"""FHIR R4 export: one citizen assessment as a Bundle.

Shaped against the OneAquaHealth IG (hl7-eu/oah) as far as that IG defines
things. See docs/fhir/README.md for what was and was not available when this was
written, and docs/fhir/validation-report.md for the validator output.

Modelling decisions worth stating plainly, because they are choices rather than
facts:

- **`Observation.performer` is a contained `Organization`**, representing the
  monitoring programme or the team, not the person. The profile requires a
  performer; StreamLens deliberately holds no identity for its citizens, so
  there is no person to name. A contained `RelatedPerson` was considered and
  rejected: `RelatedPerson.patient` is 1..1 in R4, so it would need a Patient
  that does not exist and should not be invented.
- **The citizen appears in `Provenance.agent` as a logical reference** - an
  identifier carrying the pseudonymous client id and nothing else. R4 allows a
  Reference with `identifier` and no `reference`, which is exactly the case
  where a participant is known by an id in another system but has no resource.
- **The AI appears as a contained `Device`** with the model name and the prompt
  version, with participant type `assembler`: it assembled a draft that a person
  then confirmed or overrode. It is never the author.
- Answers to choose-ALL questions become `component` entries rather than several
  codings in one `CodeableConcept`, because several codings in one concept means
  "the same concept in different systems", which is not what a multi-select is.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

CANONICAL_BASE = "https://mitalimehta02.github.io/streamlens/fhir"
# Bundle.entry.fullUrl must be an absolute URL. "urn:uuid:" is only legal in
# front of an actual UUID, so entries are addressed under a resource base and
# relative references resolve against it.
RESOURCE_BASE = "https://mitalimehta02.github.io/streamlens/fhir"
QUESTION_CS = f"{CANONICAL_BASE}/CodeSystem/citizen-question"
ANSWER_CS = f"{CANONICAL_BASE}/CodeSystem/citizen-answer"

IG_BASE = "http://hl7.eu/fhir/ig/oah"
LOCATION_PROFILE = f"{IG_BASE}/StructureDefinition/location-oah"
OBSERVATION_PROFILE = f"{IG_BASE}/StructureDefinition/observation-indicators-oah"

SITE_ID_SYSTEM = "https://api.enora-oah.eu/api/sites"
CLIENT_ID_SYSTEM = f"{CANONICAL_BASE}/pseudonymous-client"

PROVENANCE_AGENT_TYPE = "http://terminology.hl7.org/CodeSystem/provenance-participant-type"

PROGRAMME_NAME = "StreamLens citizen monitoring"


def _narrative(text: str) -> dict:
    """A minimal generated narrative, so dom-6 is satisfied.

    dom-6 is a best-practice constraint rather than a rule, but a resource a
    human cannot read is a poor export, and the text costs almost nothing.
    """
    safe = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return {
        "status": "generated",
        "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><p>{safe}</p></div>',
    }


def _instant(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _programme(team: str = "") -> dict:
    """The contained Organization used as Observation.performer."""
    name = f"{PROGRAMME_NAME} - team {team}" if team else PROGRAMME_NAME
    return {
        "resourceType": "Organization",
        "id": "programme",
        "active": True,
        "name": name,
    }


def _ai_device(model: str, prompt_version: str) -> dict:
    device: dict[str, Any] = {
        "resourceType": "Device",
        "id": "ai",
        "status": "active",
        "deviceName": [{"name": model or "unknown model", "type": "model-name"}],
    }
    if prompt_version:
        device["version"] = [{"value": prompt_version}]
    return device


def build_location(site: dict) -> dict:
    location: dict[str, Any] = {
        "resourceType": "Location",
        "id": f"site-{site['id']}",
        "meta": {"profile": [LOCATION_PROFILE]},
        "text": _narrative(
            f"OneAquaHealth research site {site['id']}: "
            f"{site.get('name') or site['id']}"
            + (f", {site['city']}" if site.get("city") else "")
        ),
        "identifier": [{"system": SITE_ID_SYSTEM, "value": site["id"]}],
        "status": "active",
        "name": site.get("name") or site["id"],
        "mode": "instance",
    }
    if site.get("city"):
        location["address"] = {
            "city": site["city"],
            "country": site.get("country") or None,
        }
        location["address"] = {k: v for k, v in location["address"].items() if v}
    if site.get("lat") is not None and site.get("lon") is not None:
        location["position"] = {
            "longitude": float(site["lon"]),
            "latitude": float(site["lat"]),
        }
        if site.get("altitude_m") is not None:
            location["position"]["altitude"] = float(site["altitude_m"])
    return location


def _answer_concept(question_id: str, code: str, display: str) -> dict:
    return {
        "coding": [{
            "system": ANSWER_CS,
            "code": f"{question_id}.{code}",
            "display": display or code,
        }],
        "text": display or code,
    }


def build_observation(
    observation_id: str,
    answer: dict,
    question: dict,
    site_id: str,
    recorded_at: datetime,
    team: str = "",
    ai_model: str = "",
    prompt_version: str = "",
) -> dict:
    """One Observation per answered question."""
    question_id = answer["question_id"]
    codes = list(answer.get("codes") or [])
    options = {o["code"]: o for o in question.get("options", [])}

    def display_for(code: str) -> str:
        option = options.get(code) or {}
        label = option.get("label")
        if isinstance(label, dict):
            return label.get("en", code)
        return label or code

    label = question.get("label")
    question_display = label.get("en", question_id) if isinstance(label, dict) else (
        label or question_id
    )

    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": f"obs-{observation_id}-{question_id}",
        "meta": {"profile": [OBSERVATION_PROFILE]},
        "text": _narrative(
            f"{question_display}: "
            + ", ".join(display_for(c) for c in codes)
            + f" (citizen-confirmed, {_instant(recorded_at)})"
        ),
        "contained": [_programme(team)],
        "status": "final",
        "code": {
            "coding": [{
                "system": QUESTION_CS,
                "code": question_id,
                "display": question_display,
            }],
            "text": question_display,
        },
        "subject": {"reference": f"Location/site-{site_id}"},
        "effectiveDateTime": _instant(recorded_at),
        "performer": [{"reference": "#programme"}],
    }

    if len(codes) == 1:
        resource["valueCodeableConcept"] = _answer_concept(
            question_id, codes[0], display_for(codes[0])
        )
    elif len(codes) > 1:
        # A choose-ALL answer: one component per selected code.
        resource["component"] = [
            {
                "code": resource["code"],
                "valueCodeableConcept": _answer_concept(
                    question_id, code, display_for(code)
                ),
            }
            for code in codes
        ]

    # What the AI proposed, recorded next to what the citizen decided.
    suggested = answer.get("ai_suggested_code")
    if suggested:
        agreed = suggested in codes
        confidence = answer.get("ai_confidence")
        text = (
            f"Citizen-confirmed answer. The AI suggested '{suggested}'"
            + (f" with confidence {confidence:.2f}" if confidence is not None else "")
            + (". The citizen agreed." if agreed else ". The citizen chose differently.")
            + (f" Model: {ai_model}." if ai_model else "")
            + (f" Prompt: {prompt_version}." if prompt_version else "")
        )
    else:
        text = "Citizen-confirmed answer. The AI made no suggestion for this question."
    resource["note"] = [{"text": text}]
    return resource


def build_provenance(
    observation_id: str,
    targets: list[str],
    recorded_at: datetime,
    client_id: str,
    ai_model: str = "",
    prompt_version: str = "",
    ai_used: bool = True,
) -> dict:
    agents: list[dict[str, Any]] = [{
        "type": {
            "coding": [{
                "system": PROVENANCE_AGENT_TYPE,
                "code": "author",
                "display": "Author",
            }]
        },
        # A logical reference: the citizen is known only by a pseudonymous id.
        # No name, no email, no Patient or RelatedPerson resource exists.
        "who": {
            "identifier": {
                "system": CLIENT_ID_SYSTEM,
                "value": client_id or "anonymous",
            },
            "display": "Citizen observer (pseudonymous)",
        },
    }]

    contained: list[dict] = []
    if ai_used and (ai_model or prompt_version):
        contained.append(_ai_device(ai_model, prompt_version))
        agents.append({
            "type": {
                "coding": [{
                    "system": PROVENANCE_AGENT_TYPE,
                    "code": "assembler",
                    "display": "Assembler",
                }]
            },
            "who": {"reference": "#ai"},
        })

    provenance: dict[str, Any] = {
        "resourceType": "Provenance",
        "id": f"prov-{observation_id}",
        "text": _narrative(
            "Answers confirmed by a pseudonymous citizen observer"
            + (f"; draft suggestions assembled by {ai_model}" if ai_used and ai_model
               else "")
            + (f" using prompt {prompt_version}" if ai_used and prompt_version else "")
            + "."
        ),
        "target": [{"reference": reference} for reference in targets],
        "recorded": _instant(recorded_at),
        "agent": agents,
    }
    if contained:
        provenance["contained"] = contained
    return provenance


def build_bundle(
    observation: dict,
    site: dict,
    questions_by_id: dict[str, dict],
    team: str = "",
    prompt_version: str = "",
) -> dict:
    """A whole assessment as a collection Bundle."""
    recorded_at = observation["recorded_at"]
    if isinstance(recorded_at, str):
        recorded_at = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))

    location = build_location(site)
    entries: list[dict] = [{
        "fullUrl": f"{RESOURCE_BASE}/Location/site-{site['id']}",
        "resource": location,
    }]

    targets: list[str] = []
    for answer in observation.get("answers", []):
        question = questions_by_id.get(answer["question_id"])
        if question is None or not answer.get("codes"):
            continue
        resource = build_observation(
            observation["id"], answer, question, site["id"], recorded_at,
            team=team, ai_model=observation.get("ai_model", ""),
            prompt_version=prompt_version,
        )
        entries.append({
            "fullUrl": f"{RESOURCE_BASE}/Observation/{resource['id']}",
            "resource": resource,
        })
        targets.append(f"Observation/{resource['id']}")

    # The citizen's own overall rating, recorded like any other answer but
    # never as an AI suggestion - the AI is not allowed to propose it.
    overall_question = questions_by_id.get("overall")
    if overall_question and observation.get("overall"):
        resource = build_observation(
            observation["id"],
            {"question_id": "overall", "codes": [observation["overall"]]},
            overall_question, site["id"], recorded_at, team=team,
        )
        resource["note"] = [{
            "text": "The citizen's own overall rating. StreamLens never lets the AI "
                    "suggest this value."
        }]
        entries.append({
            "fullUrl": f"{RESOURCE_BASE}/Observation/{resource['id']}",
            "resource": resource,
        })
        targets.append(f"Observation/{resource['id']}")

    provenance = build_provenance(
        observation["id"],
        targets + [f"Location/site-{site['id']}"],
        recorded_at,
        observation.get("client_id", ""),
        ai_model=observation.get("ai_model", ""),
        prompt_version=prompt_version,
        ai_used=bool(observation.get("ai_provider")),
    )
    entries.append({
        "fullUrl": f"{RESOURCE_BASE}/Provenance/{provenance['id']}",
        "resource": provenance,
    })

    return {
        "resourceType": "Bundle",
        "id": f"streamlens-{observation['id']}",
        "type": "collection",
        "timestamp": _instant(datetime.now(timezone.utc)),
        "entry": entries,
    }
