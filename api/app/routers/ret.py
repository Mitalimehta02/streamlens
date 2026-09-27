"""Return: quests, points, the team leaderboard, wellbeing, and FHIR export.

Names the third part of the loop - what StreamLens gives back to the people who
contributed. The scoring and ranking constraints live in app/points.py; this
router is the plumbing.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, select

from ..config import Settings, get_settings
from ..fhir import build_bundle
from ..ai.gemini import prompt_version
from ..models import (
    Observation,
    ObservationAnswer,
    ObservationPhoto,
    get_session,
)
from ..points import (
    MIN_GROUP,
    ObservationInput,
    coverage,
    get_points_rules,
    MIN_TEAM_MEMBERS,
    leaderboard,
    score_observations,
    withheld_teams,
    wellbeing,
)
from ..questions import QuestionSet, get_questions
from ..quests import SiteHistory, get_quest_rules, rank
from ..quests import for_site as quests_for_site
from ..sites import SiteSet, get_sites, haversine_m
from ..weather import get_forecast

router = APIRouter(tags=["return"])

SEWAGE_QUESTIONS = {"sewage": {"Y"}, "pollutedPipes": {"Y"}}

DataScope = Query(
    default="all",
    description="Which records to use: 'all', 'real' or 'demo'. Echoed back.",
)


def _scope(statement, scope: str):
    if scope == "real":
        return statement.where(Observation.synthetic == False)  # noqa: E712
    if scope == "demo":
        return statement.where(Observation.synthetic == True)  # noqa: E712
    return statement


def _utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def _load_all(session: Session, scope: str) -> tuple[list[Observation], dict[str, list]]:
    observations = session.exec(_scope(select(Observation), scope)).all()
    ids = [o.id for o in observations]
    answers: dict[str, list] = defaultdict(list)
    if ids:
        for answer in session.exec(
            select(ObservationAnswer).where(ObservationAnswer.observation_id.in_(ids))
        ).all():
            answers[answer.observation_id].append(answer)
    return list(observations), answers


def _histories(
    observations: list[Observation], answers: dict[str, list], site_set: SiteSet
) -> dict[str, SiteHistory]:
    histories: dict[str, SiteHistory] = {}
    for observation in observations:
        site = site_set.get(observation.site_id)
        if site is None:
            continue
        history = histories.setdefault(observation.site_id, SiteHistory(site=site))
        when = _utc(observation.recorded_at)
        history.visit_dates.append(when)
        history.observers_by_date.append((when, observation.client_id or ""))
        for answer in answers.get(observation.id, []):
            wanted = SEWAGE_QUESTIONS.get(answer.question_id)
            if wanted and set(answer.codes) & wanted:
                history.sewage_reports.append(when)
    return histories


# --------------------------------------------------------------------------
# Quests
# --------------------------------------------------------------------------

@router.get("/quests")
def list_quests(
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    city: str | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=60),
    scope: str = DataScope,
    site_set: SiteSet = Depends(get_sites),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict:
    """Open quests, most urgent first, one per site."""
    observations, answers = _load_all(session, scope)
    histories = _histories(observations, answers, site_set)

    if city:
        histories = {
            k: v for k, v in histories.items()
            if v.site.get("city", "").lower() == city.lower()
        }

    # Only fetch weather for sites where the after-rain rule could possibly
    # apply; a site with no sewage report can never trigger it.
    found = []
    for site_id, history in histories.items():
        forecast = None
        if history.sewage_reports:
            forecast = get_forecast(
                session, site_id, history.site.get("lat"), history.site.get("lon"),
                cache_seconds=settings.weather_cache_seconds,
            )
        found.extend(quests_for_site(history, forecast))

    ordered = rank(found)

    if lat is not None and lon is not None:
        def distance(quest) -> float:
            if quest.lat is None or quest.lon is None:
                return float("inf")
            return haversine_m(lat, lon, quest.lat, quest.lon) / 1000
        ordered.sort(key=lambda q: (q.priority, distance(q)))
        payload = []
        for quest in ordered[:limit]:
            item = asdict(quest)
            km = distance(quest)
            item["distance_km"] = round(km, 1) if km != float("inf") else None
            payload.append(item)
    else:
        payload = [asdict(q) for q in ordered[:limit]]

    return {
        "scope": scope,
        "count": len(payload),
        "total_open": len(ordered),
        "principle": get_quest_rules().doc.get("principle", []),
        "quests": payload,
    }


@router.get("/sites/{site_id}/quests")
def site_quests(
    site_id: str,
    scope: str = DataScope,
    site_set: SiteSet = Depends(get_sites),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict:
    site = site_set.get(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"unknown site '{site_id}'")

    observations, answers = _load_all(session, scope)
    histories = _histories(observations, answers, site_set)
    history = histories.get(site_id, SiteHistory(site=site))

    forecast = None
    if history.sewage_reports:
        forecast = get_forecast(
            session, site_id, site.get("lat"), site.get("lon"),
            cache_seconds=settings.weather_cache_seconds,
        )
    found = quests_for_site(history, forecast)
    return {"site_id": site_id, "scope": scope,
            "quests": [asdict(q) for q in found]}


# --------------------------------------------------------------------------
# Points, teams, coverage
# --------------------------------------------------------------------------

def _score_inputs(
    session: Session, observations: list[Observation], answers: dict[str, list]
) -> list[ObservationInput]:
    ids = [o.id for o in observations]
    photos: dict[str, list] = defaultdict(list)
    if ids:
        for photo in session.exec(
            select(ObservationPhoto).where(ObservationPhoto.observation_id.in_(ids))
        ).all():
            photos[photo.observation_id].append(photo)

    settings = get_settings()
    out = []
    for observation in observations:
        photo_rows = photos.get(observation.id, [])
        out.append(ObservationInput(
            id=observation.id,
            site_id=observation.site_id,
            client_id=observation.client_id or "",
            recorded_at=_utc(observation.recorded_at),
            photos_ok=[
                p.blur_score >= settings.blur_threshold
                and settings.dark_threshold <= p.brightness <= settings.bright_threshold
                for p in photo_rows
            ],
            answers={a.question_id: a.codes for a in answers.get(observation.id, [])},
            completed_quest=observation.completed_quest or None,
            synthetic=observation.synthetic,
            team=observation.team or "",
        ))
    return out


@router.get("/leaderboard")
def team_leaderboard(
    city: str | None = Query(default=None),
    scope: str = DataScope,
    site_set: SiteSet = Depends(get_sites),
    session: Session = Depends(get_session),
) -> dict:
    """Teams only. Individuals are never ranked - see app/points.py for why."""
    observations, answers = _load_all(session, scope)
    inputs = _score_inputs(session, observations, answers)
    scored = score_observations(inputs)
    site_city = {s["id"]: s.get("city", "") for s in site_set.all()}

    standings = leaderboard(inputs, scored, city=city, site_city=site_city)
    withheld = withheld_teams(inputs, scored, city=city, site_city=site_city)
    rules = get_points_rules()
    return {
        "scope": scope,
        "city": city,
        "teams": [asdict(t) for t in standings],
        "team_count": len(standings),
        "individuals_ranked": False,
        "min_team_members": MIN_TEAM_MEMBERS,
        "teams_withheld_too_small": withheld,
        "why_withheld": (
            f"Teams with fewer than {MIN_TEAM_MEMBERS} people are not ranked: a team "
            "of one is an individual ranking by another name."
        ),
        "why_teams_only": (
            "Ranking individuals on a scientific dataset rewards whoever submits "
            "most, and the fastest way to submit most is to stop looking properly."
        ),
        "why_not_volume": rules.doc.get("why_not_volume", []),
        "daily_cap": rules.daily_cap,
    }


@router.get("/coverage")
def coverage_map(
    city: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    scope: str = DataScope,
    site_set: SiteSet = Depends(get_sites),
    session: Session = Depends(get_session),
) -> dict:
    observations, answers = _load_all(session, scope)
    inputs = _score_inputs(session, observations, answers)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    payload = coverage(inputs, site_set.all(), since, city=city)
    payload["scope"] = scope
    payload["days"] = days
    return payload


@router.get("/points/me")
def my_points(
    client_id: str = Query(..., description="The caller's pseudonymous id."),
    scope: str = DataScope,
    session: Session = Depends(get_session),
) -> dict:
    observations, answers = _load_all(session, scope)
    inputs = _score_inputs(session, observations, answers)
    scored = score_observations(inputs)
    mine = [s for s in scored if s.client_id == client_id]
    rules = get_points_rules()
    return {
        "client_id": client_id,
        "scope": scope,
        "total_points": sum(s.points for s in mine),
        "observations": len(mine),
        "daily_cap": rules.daily_cap,
        "awards": [asdict(s) for s in sorted(
            mine, key=lambda s: s.recorded_at, reverse=True)[:20]],
        "why_not_volume": rules.doc.get("why_not_volume", []),
        "never_awarded_for": rules.doc.get("never_awarded_for", []),
    }


# --------------------------------------------------------------------------
# Wellbeing mirror
# --------------------------------------------------------------------------

@router.get("/wellbeing")
def wellbeing_mirror(
    client_id: str | None = Query(default=None),
    community: bool = Query(default=False),
    city: str | None = Query(default=None),
    scope: str = DataScope,
    site_set: SiteSet = Depends(get_sites),
    session: Session = Depends(get_session),
) -> dict:
    observations, _ = _load_all(session, scope)
    site_city = {s["id"]: s.get("city", "") for s in site_set.all()}

    rows = []
    for observation in observations:
        if city and site_city.get(observation.site_id, "").lower() != city.lower():
            continue
        if not community and client_id and observation.client_id != client_id:
            continue
        rows.append((observation.client_id or "", observation.overall,
                     observation.emotions))

    mirror = wellbeing(rows, scope="community" if community else "personal")
    payload = asdict(mirror)
    payload["scope"] = scope
    payload["city"] = city
    payload["research_link"] = {
        "text": "OneAquaHealth studies the links between urban stream condition and "
                "human wellbeing.",
        "url": "https://www.oneaquahealth.eu/",
    }
    payload["not_a_health_measure"] = (
        "This describes recorded feelings, not health. StreamLens does not "
        "diagnose, and does not claim a stream caused a feeling."
    )
    return payload


# --------------------------------------------------------------------------
# FHIR export
# --------------------------------------------------------------------------

def _bundle_for(session: Session, observation_id: str, site_set: SiteSet,
                questions: QuestionSet) -> dict:
    observation = session.get(Observation, observation_id)
    if observation is None:
        raise HTTPException(status_code=404, detail="no such observation")
    site = site_set.get(observation.site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="the site for this observation is unknown")

    answers = session.exec(
        select(ObservationAnswer).where(
            ObservationAnswer.observation_id == observation_id)
    ).all()

    payload = {
        "id": observation.id,
        "overall": observation.overall,
        "recorded_at": _utc(observation.recorded_at),
        "client_id": observation.client_id,
        "ai_provider": observation.ai_provider,
        "ai_model": observation.ai_model,
        "answers": [
            {
                "question_id": a.question_id,
                "codes": a.codes,
                "ai_suggested_code": a.ai_suggested_code,
                "ai_confidence": a.ai_confidence,
            }
            for a in answers
        ],
    }
    questions_by_id = {q.id: q.raw for q in questions.questions.values()}
    return build_bundle(
        payload, site, questions_by_id,
        team=observation.team or "",
        prompt_version=prompt_version(),
    )


@router.get("/observations/{observation_id}/fhir")
def observation_fhir(
    observation_id: str,
    site_set: SiteSet = Depends(get_sites),
    questions: QuestionSet = Depends(get_questions),
    session: Session = Depends(get_session),
) -> Response:
    bundle = _bundle_for(session, observation_id, site_set, questions)
    return Response(
        content=json.dumps(bundle, ensure_ascii=False, indent=2),
        media_type="application/fhir+json",
        headers={
            "Content-Disposition":
                f'attachment; filename="streamlens-{observation_id}.fhir.json"'
        },
    )


@router.get("/cities/{city}/fhir")
def city_fhir(
    city: str,
    limit: int = Query(default=25, ge=1, le=200),
    scope: str = DataScope,
    site_set: SiteSet = Depends(get_sites),
    questions: QuestionSet = Depends(get_questions),
    session: Session = Depends(get_session),
) -> Response:
    """Every recent assessment in a city, as one Bundle of Bundles."""
    site_ids = [s["id"] for s in site_set.all()
                if s.get("city", "").lower() == city.lower()]
    if not site_ids:
        raise HTTPException(status_code=404, detail=f"unknown city '{city}'")

    statement = _scope(
        select(Observation).where(Observation.site_id.in_(site_ids)), scope
    ).order_by(Observation.recorded_at.desc()).limit(limit)

    entries = []
    for observation in session.exec(statement).all():
        bundle = _bundle_for(session, observation.id, site_set, questions)
        entries.append({
            "fullUrl": f"https://mitalimehta02.github.io/streamlens/fhir/Bundle/{bundle['id']}",
            "resource": bundle,
        })

    outer = {
        "resourceType": "Bundle",
        "id": f"streamlens-{city.lower()}",
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "entry": entries,
    }
    return Response(
        content=json.dumps(outer, ensure_ascii=False, indent=2),
        media_type="application/fhir+json",
        headers={
            "Content-Disposition":
                f'attachment; filename="streamlens-{city.lower()}.fhir.json"'
        },
    )
