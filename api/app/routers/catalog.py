"""GET /sites, GET /questions and GET /health - all served from local files."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..ai.factory import get_provider
from ..ai.gemini import prompt_version
from ..config import Settings, get_settings
from ..questions import QuestionSet, get_questions
from ..schemas import HealthResponse, SitesResponse
from ..sites import SiteSet, get_sites

router = APIRouter(tags=["catalog"])

VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_settings),
    questions: QuestionSet = Depends(get_questions),
    site_set: SiteSet = Depends(get_sites),
) -> HealthResponse:
    provider = get_provider(settings)
    return HealthResponse(
        status="ok",
        version=VERSION,
        ai_provider=provider.name,
        ai_model=provider.model,
        ai_is_mock=provider.is_mock,
        questions=len(questions.questions),
        sites=len(site_set.sites),
        prompt_version=prompt_version(),
        cors_origins=settings.cors_origin_list,
    )


@router.get("/sites", response_model=SitesResponse)
def list_sites(
    city: str | None = Query(default=None, description="Filter by city name."),
    site_set: SiteSet = Depends(get_sites),
) -> SitesResponse:
    sites = site_set.all()
    if city:
        wanted = city.strip().lower()
        sites = [s for s in sites if s.get("city", "").lower() == wanted]

    meta = site_set.meta
    return SitesResponse(
        attribution=meta["attribution"],
        source=meta["source"],
        fetched_at=meta["fetched_at"],
        count=len(sites),
        cities=meta["cities"],
        synthetic=meta["synthetic"],
        sites=sites,
    )


@router.get("/questions")
def list_questions(
    lang: str = Query(default="en", description="en, pt, it, fr, nl or no."),
    questions: QuestionSet = Depends(get_questions),
) -> dict:
    """The question catalogue in one language, with glossary and provenance.

    Not typed as a response model on purpose: the payload is a localised copy of
    data/questions.json, and pinning a schema here would mean editing Python
    every time the JSON gains a field.
    """
    return questions.localized(lang)
