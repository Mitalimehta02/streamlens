"""Settings, read from api/.env. Secrets never live anywhere else."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parent
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- AI provider -------------------------------------------------------
    ai_provider: str = "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    # A citizen standing in the rain does not wait indefinitely for a model.
    gemini_timeout_s: float = 20.0
    # Number of RETRIES after the first attempt, so 1 means two attempts.
    gemini_retries: int = 1
    # Base for exponential backoff between retries, with jitter.
    gemini_backoff_base_s: float = 0.6
    # Which prompt in app/ai/prompts/ to use, without the .md.
    assess_prompt: str = "assess_v3"

    # --- Weather ------------------------------------------------------------
    # How long an Open-Meteo forecast is reused before refetching.
    weather_cache_seconds: int = 3600

    # --- Storage -----------------------------------------------------------
    database_url: str = "sqlite:///./streamlens.db"
    upload_dir: str = "./uploads"

    # --- CORS --------------------------------------------------------------
    # A comma-separated string, deliberately not a list[str]: pydantic-settings
    # parses a list-typed field from the environment as JSON, so a plain
    # comma-separated CORS_ORIGINS would fail to parse and take the whole
    # service down at start-up. The splitting happens in cors_origin_list.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Photo handling ----------------------------------------------------
    max_image_px: int = 1600
    # A SEPARATE, smaller copy is what gets sent to the AI. Nothing larger than
    # this ever leaves the server for Google, whatever we keep ourselves.
    ai_max_image_px: int = 1024
    # Largest upload accepted, in megabytes.
    max_upload_mb: int = 8
    # Whether photo bytes are kept at all. False on the hosted demo: the quality
    # metrics are kept and the image is discarded.
    store_photos: bool = True
    # Stored photos are deleted after this many days.
    photo_retention_days: int = 14
    blur_threshold: float = 100.0
    dark_threshold: float = 45.0
    bright_threshold: float = 225.0

    # How far from the recorded site coordinates we start warning, in metres.
    gps_warn_m: float = 250.0

    # Below this confidence a suggestion is flagged for the citizen's attention.
    low_confidence: float = 0.55

    # --- Protecting a free-tier API key -------------------------------------
    # Per-caller and whole-service limits on AI calls. When either is reached
    # the request still succeeds, on the mock, with a visible notice.
    ai_calls_per_hour_per_client: int = 10
    ai_calls_per_day_total: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        """The database URL, ready for SQLAlchemy.

        Two corrections happen here. A relative SQLite path is pinned to api/,
        because without it the database file lands wherever the process was
        started from, so `npm run dev` and `python scripts/seed_demo.py` quietly
        used two different files and the demo data appeared to vanish. And a
        hosted Postgres URL, which providers hand out as `postgres://` or
        `postgresql://`, is given the driver this project actually installs, so
        the same string can be pasted straight from Neon into the environment.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]

        prefix = "sqlite:///"
        if not url.startswith(prefix):
            return url
        raw = url[len(prefix):]
        if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
            return url  # already absolute
        return prefix + str((API_DIR / raw.lstrip("./")).resolve())

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = API_DIR / path
        return path

    @property
    def use_gemini(self) -> bool:
        """Gemini is used only when it is both asked for and actually usable.

        Anything else falls back to the mock provider, which the UI labels.
        """
        return self.ai_provider.lower() == "gemini" and bool(self.gemini_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
