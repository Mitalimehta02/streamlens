"""Request and response shapes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EMOTIONS = ("joy", "serenity", "anger", "fear")


# --------------------------------------------------------------------------
# Sites and questions
# --------------------------------------------------------------------------

class SiteOut(BaseModel):
    id: str
    name: str
    city: str
    city_id: str = ""
    country: str = ""
    lang: str = "en"
    lat: float | None = None
    lon: float | None = None
    altitude_m: float | None = None


class SitesResponse(BaseModel):
    attribution: str
    source: str | None = None
    fetched_at: str | None = None
    count: int
    cities: list[str] = []
    synthetic: bool = False
    sites: list[SiteOut]


# --------------------------------------------------------------------------
# Suggestions
# --------------------------------------------------------------------------

class QualityIssueOut(BaseModel):
    code: str
    severity: Literal["warn", "block"]
    message: str


class PhotoQualityOut(BaseModel):
    role: str
    width: int
    height: int
    blur_score: float = Field(description="Variance of the Laplacian; lower means blurrier.")
    brightness: float = Field(description="Mean luma, 0-255.")
    issues: list[QualityIssueOut] = []
    ok: bool
    exif_stripped: bool = True


class LocationCheck(BaseModel):
    provided: bool
    distance_m: float | None = None
    far_from_site: bool = False
    message: str = ""


class SuggestionChip(BaseModel):
    """One AI proposal, already validated against questions.json."""

    question_id: str
    suggested_code: str
    additional_codes: list[str] = Field(
        default_factory=list,
        description="Further codes for choose-ALL questions. Empty for single-answer ones.",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    needs_review: bool
    review_reason: str = ""


class DroppedSuggestion(BaseModel):
    """A proposal that failed validation and never reached the citizen."""

    question_id: str
    codes: list[str]
    why: str


class UsageOut(BaseModel):
    prompt_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    total_tokens: int = 0


class SuggestResponse(BaseModel):
    site_id: str
    site_name: str = ""
    provider: str = Field(description="The provider that actually produced these.")
    requested_provider: str = Field(
        default="", description="The provider the server was configured to use."
    )
    model: str
    is_mock: bool = Field(
        description="True when the demo heuristic produced these, not a vision model. "
        "The UI must show a badge when this is true."
    )
    degraded: bool = Field(
        default=False,
        description="True when the configured provider failed and the mock stood in. "
        "The UI must tell the citizen to answer manually.",
    )
    degraded_reason: str = Field(
        default="", description="Plain-language reason, safe to show a citizen."
    )
    degraded_kind: str = Field(
        default="", description="timeout | transport | auth | bad_output | other"
    )
    is_watercourse: bool = Field(
        default=True,
        description="False when the photo does not show a stream at all. The UI must "
        "then show no chips and ask for a different photo.",
    )
    not_watercourse_reason: str = ""
    attempts: int = 1
    latency_ms: int = 0
    usage: UsageOut = Field(default_factory=UsageOut)
    ai_calls_remaining_today: int = Field(
        default=0,
        description="Free-tier allowance left today across the whole demo.",
    )
    prompt_version: str
    provider_note: str = ""
    generated_at: datetime
    photo_quality: list[PhotoQualityOut] = []
    location: LocationCheck
    suggestions: list[SuggestionChip] = []
    dropped: list[DroppedSuggestion] = []
    notice: str = (
        "These are suggestions only. Every answer is yours to confirm, change or reject, "
        "and the overall rating is never suggested."
    )


# --------------------------------------------------------------------------
# Observations
# --------------------------------------------------------------------------

class AnswerIn(BaseModel):
    question_id: str
    codes: list[str] = Field(min_length=1)
    # What the AI had proposed, kept so agreement can be measured later.
    ai_suggested_code: str | None = None
    ai_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @property
    def agreed_with_ai(self) -> bool | None:
        if self.ai_suggested_code is None:
            return None
        return self.ai_suggested_code in self.codes


class ObservationIn(BaseModel):
    site_id: str
    overall: str = Field(description="The citizen's rating: GOOD, MODERATE or POOR.")
    answers: list[AnswerIn] = []
    emotions: dict[str, int] = Field(default_factory=dict)
    lang: str = "en"
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: float | None = None
    note: str = ""
    consent_given: bool = Field(
        description="The citizen saw the consent notice and agreed. Required."
    )
    synthetic: bool = False
    client_id: str = ""
    team: str = Field(default="", max_length=40,
                      description="Optional team or school code. Not an account.")
    completed_quest: str = Field(default="", max_length=40)
    recorded_at: datetime | None = None
    ai_provider: str = ""
    ai_model: str = ""

    @field_validator("emotions")
    @classmethod
    def check_emotions(cls, value: dict[str, int]) -> dict[str, int]:
        for name, level in value.items():
            if name not in EMOTIONS:
                raise ValueError(f"unknown emotion '{name}'; expected one of {EMOTIONS}")
            if not 0 <= level <= 4:
                raise ValueError(f"emotion '{name}' must be between 0 and 4, got {level}")
        return value

    @field_validator("consent_given")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("an observation cannot be stored without consent")
        return value

    @field_validator("recorded_at")
    @classmethod
    def default_recorded_at(cls, value: datetime | None) -> datetime:
        return value or datetime.now(timezone.utc)


class ObservationAnswerOut(BaseModel):
    question_id: str
    codes: list[str]
    ai_suggested_code: str | None = None
    ai_confidence: float | None = None
    agreed_with_ai: bool | None = None


class ObservationOut(BaseModel):
    id: str
    site_id: str
    site_name: str = ""
    overall: str
    emotions: dict[str, int] = {}
    answers: list[ObservationAnswerOut] = []
    lang: str = "en"
    lat: float | None = None
    lon: float | None = None
    note: str = ""
    synthetic: bool = False
    ai_provider: str = ""
    ai_model: str = ""
    photos: list[PhotoQualityOut] = []
    recorded_at: datetime
    created_at: datetime
    ai_agreement: float | None = Field(
        default=None,
        description="Share of answered AI suggestions the citizen kept, 0-1. "
        "Null when the AI suggested nothing.",
    )


class ObservationSummary(BaseModel):
    id: str
    site_id: str
    site_name: str = ""
    overall: str
    synthetic: bool
    recorded_at: datetime


class HealthResponse(BaseModel):
    status: str
    version: str
    ai_provider: str
    ai_model: str
    ai_is_mock: bool
    questions: int
    sites: int
    prompt_version: str
    cors_origins: list[str] = Field(
        default_factory=list,
        description=(
            "Origins this service answers browser requests from. Listed because "
            "a misconfigured CORS_ORIGINS is otherwise invisible: the browser "
            "reports only a blocked request, and the service looks healthy. Not "
            "a secret - the allow-origin header already reveals it one origin "
            "at a time."
        ),
    )
