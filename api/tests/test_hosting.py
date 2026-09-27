"""What changes when StreamLens is hosted rather than run on a laptop.

Three promises are made on the hosted demo, and each is checked here: the
database URL a provider hands out works as pasted, photographs are not stored
at all, and any that were stored are deleted once past their keep-by date.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app import retention
from app.config import API_DIR, Settings, get_settings

REPO_ROOT = API_DIR.parent
from app.main import create_app
from app.models import Observation, ObservationPhoto, set_engine
from tests.conftest import sharp_image


# --------------------------------------------------------------- database URL

@pytest.mark.parametrize(
    "given, expected",
    [
        # What Neon and Render actually print, including the older scheme.
        (
            "postgresql://user:pw@ep-cool-1.eu-central-1.aws.neon.tech/db?sslmode=require",
            "postgresql+psycopg://user:pw@ep-cool-1.eu-central-1.aws.neon.tech/db?sslmode=require",
        ),
        (
            "postgres://user:pw@host/db",
            "postgresql+psycopg://user:pw@host/db",
        ),
        # An explicit driver is left exactly as the operator wrote it.
        (
            "postgresql+psycopg://user:pw@host/db",
            "postgresql+psycopg://user:pw@host/db",
        ),
    ],
)
def test_a_hosted_database_url_works_as_pasted(given, expected):
    assert Settings(database_url=given).resolved_database_url == expected


def test_a_postgres_url_is_not_mistaken_for_sqlite():
    assert Settings(database_url="postgres://user:pw@host/db").is_sqlite is False
    assert Settings(database_url="sqlite:///./streamlens.db").is_sqlite is True


def test_a_relative_sqlite_path_is_still_pinned_to_the_api_folder():
    resolved = Settings(database_url="sqlite:///./streamlens.db").resolved_database_url
    assert resolved.startswith("sqlite:///")
    assert resolved.endswith("streamlens.db")
    assert "api" in resolved.replace("\\", "/").lower()


def test_a_postgres_engine_can_actually_be_built():
    """The driver is installed and the SQLite-only argument is not passed.

    create_engine does not connect, so this needs no server: it fails if the
    psycopg dialect is missing. The SQLite-only check_same_thread argument is
    kept away from it by is_sqlite, checked above; passing it here would fail
    only on the first real connection, which is too late to find out.
    """
    from app.models import get_engine, set_engine

    set_engine(None)
    try:
        engine = get_engine(Settings(database_url="postgres://u:p@localhost/streamlens"))
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
        # Neon suspends its compute when idle and drops the connections with
        # it, so a pooled connection is tested before it is handed out.
        assert engine.pool._pre_ping is True
        assert engine.pool._recycle == 300
    finally:
        set_engine(None)


# --------------------------------------------------------------------- CORS

def test_health_reports_the_origins_the_service_answers(client, settings):
    """A misconfigured CORS list is otherwise invisible from outside.

    The browser reports only a blocked request and the service still looks
    healthy, so the one thing an operator needs - what the running process
    thinks its allow-list is - was impossible to see without shell access.
    """
    body = client.get("/health").json()
    assert body["cors_origins"] == settings.cors_origin_list
    assert body["cors_origins"], "a service with no allowed origin answers no browser"


def test_the_origin_list_is_split_and_trimmed(client):
    """Pasted values arrive with stray spaces; empty entries are not origins."""
    parsed = Settings(
        cors_origins=" https://streamlens-ten.vercel.app , http://localhost:5173 ,,"
    ).cors_origin_list
    assert parsed == ["https://streamlens-ten.vercel.app", "http://localhost:5173"]


# The value committed in render.yaml. Kept here verbatim so that changing one
# without the other fails a test rather than a deployment.
RENDER_YAML_CORS = (
    "https://streamlens-ten.vercel.app,http://localhost:5173,http://127.0.0.1:5173"
)


def test_the_committed_origins_survive_the_environment(monkeypatch):
    """The comma-separated form has to work as an environment variable.

    This is the path a deployment actually takes, and it is not the same path as
    passing the value to the constructor: pydantic-settings parses a list-typed
    field from the environment as JSON, so had cors_origins been declared
    list[str] this exact string would raise at start-up rather than parse. The
    field is a plain str for that reason, and this test is what says so.

    _env_file=None keeps a developer's own api/.env out of the result.
    """
    monkeypatch.setenv("CORS_ORIGINS", RENDER_YAML_CORS)
    settings = Settings(_env_file=None)

    assert settings.cors_origin_list == [
        "https://streamlens-ten.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_render_yaml_is_the_source_of_these_origins():
    """The blueprint and the test agree, or one of them is wrong.

    The service is Blueprint-managed: a value typed into the Render dashboard
    against a `sync: false` key never reached the process, and the only symptom
    was every browser request being refused by a service that otherwise looked
    healthy. The file is the source of truth now, so the file is what is read.
    """
    blueprint = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    assert f"value: {RENDER_YAML_CORS}" in blueprint, (
        "render.yaml no longer sets CORS_ORIGINS to the value this suite checks"
    )
    assert "https://streamlens-ten.vercel.app" in RENDER_YAML_CORS


def test_the_deployed_origin_is_not_a_wildcard():
    """A wildcard would let any site on the internet spend the Gemini quota."""
    origins = Settings(cors_origins=RENDER_YAML_CORS).cors_origin_list
    assert "*" not in origins
    assert all(o.startswith("http://") or o.startswith("https://") for o in origins)
    assert not any(o.endswith("/") for o in origins), "a trailing slash never matches"


# ------------------------------------------------------------- STORE_PHOTOS

@pytest.fixture
def no_storage_client(tmp_path):
    """A client configured the way the hosted demo is."""
    settings = Settings(
        ai_provider="mock",
        gemini_api_key="",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        upload_dir=str(tmp_path / "uploads"),
        store_photos=False,
        ai_calls_per_hour_per_client=10_000,
        ai_calls_per_day_total=10_000,
    )
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    set_engine(engine)
    SQLModel.metadata.create_all(engine)

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client, settings, engine
    app.dependency_overrides.clear()
    set_engine(None)


def _payload(site_id: str) -> dict:
    return {
        "site_id": site_id,
        "overall": "GOOD",
        "consent_given": True,
        "answers": [{"question_id": "channelType", "codes": ["NAT"]}],
    }


def test_no_photo_bytes_are_written_when_storage_is_off(no_storage_client, site_id):
    client, settings, engine = no_storage_client

    response = client.post(
        "/observations",
        data={"payload": json.dumps(_payload(site_id))},
        files=[("upstream", ("upstream.jpg", sharp_image(), "image/jpeg"))],
    )
    assert response.status_code == 201

    # Nothing on disk, not even the folder.
    assert not settings.upload_path.exists() or not list(settings.upload_path.iterdir())

    # The measurement survives, so a reviewer can still tell whether the
    # assessment rested on a usable photograph.
    with Session(engine) as session:
        photo = session.exec(select(ObservationPhoto)).one()
    assert photo.filename == ""
    assert photo.bytes_stored == 0
    assert photo.width > 0
    assert photo.blur_score > 0
    assert photo.exif_stripped is True


def test_photo_quality_still_reaches_the_response_without_storage(
    no_storage_client, site_id
):
    client, _, _ = no_storage_client
    body = client.post(
        "/observations",
        data={"payload": json.dumps(_payload(site_id))},
        files=[("upstream", ("upstream.jpg", sharp_image(), "image/jpeg"))],
    ).json()

    assert len(body["photos"]) == 1
    photo = body["photos"][0]
    assert photo["ok"] is True
    assert photo["blur_score"] > 0
    assert photo["exif_stripped"] is True


# ------------------------------------------------------------------ sweeping

def _stored_photo(session, settings, *, age_days: float, site_id: str) -> str:
    """Write a photo file and the rows that point at it. Returns the filename."""
    when = datetime.now(timezone.utc) - timedelta(days=age_days)
    observation = Observation(
        site_id=site_id,
        overall="GOOD",
        consent_given=True,
        recorded_at=when.replace(tzinfo=None),
        created_at=when.replace(tzinfo=None),
    )
    session.add(observation)
    session.commit()

    settings.upload_path.mkdir(parents=True, exist_ok=True)
    filename = f"{observation.id}_upstream.jpg"
    (settings.upload_path / filename).write_bytes(b"not really a jpeg")
    session.add(
        ObservationPhoto(
            observation_id=observation.id,
            role="upstream",
            filename=filename,
            width=800,
            height=600,
            blur_score=180.0,
            brightness=120.0,
            bytes_stored=17,
        )
    )
    session.commit()
    return filename


def test_photos_past_the_retention_window_are_deleted(client, settings, site_id):
    retention.reset_for_tests()
    engine = create_engine(
        settings.resolved_database_url, connect_args={"check_same_thread": False}
    )
    with Session(engine) as session:
        old = _stored_photo(session, settings, age_days=20, site_id=site_id)
        fresh = _stored_photo(session, settings, age_days=2, site_id=site_id)

        assert retention.sweep(session, settings) == 1

    assert not (settings.upload_path / old).exists()
    assert (settings.upload_path / fresh).exists()

    with Session(engine) as session:
        rows = {r.filename for r in session.exec(select(ObservationPhoto)).all()}
    # The swept row keeps its measurements and loses only its file.
    assert rows == {"", fresh}


def test_the_boundary_is_the_retention_day_itself(client, settings, site_id):
    """A photo exactly at the window is kept; a moment past it is not."""
    retention.reset_for_tests()
    engine = create_engine(
        settings.resolved_database_url, connect_args={"check_same_thread": False}
    )
    with Session(engine) as session:
        just_inside = _stored_photo(
            session, settings, age_days=settings.photo_retention_days - 0.01,
            site_id=site_id,
        )
        just_outside = _stored_photo(
            session, settings, age_days=settings.photo_retention_days + 0.01,
            site_id=site_id,
        )
        assert retention.sweep(session, settings) == 1

    assert (settings.upload_path / just_inside).exists()
    assert not (settings.upload_path / just_outside).exists()


def test_the_sweep_does_not_run_twice_in_an_hour(client, settings, site_id):
    retention.reset_for_tests()
    engine = create_engine(
        settings.resolved_database_url, connect_args={"check_same_thread": False}
    )
    with Session(engine) as session:
        _stored_photo(session, settings, age_days=30, site_id=site_id)
        assert retention.sweep_if_due(session, settings) == 1

        second = _stored_photo(session, settings, age_days=30, site_id=site_id)
        # Due again only after MIN_INTERVAL_S, so this one waits its turn.
        assert retention.sweep_if_due(session, settings) == 0
        assert (settings.upload_path / second).exists()

        retention.reset_for_tests()
        assert retention.sweep_if_due(session, settings) == 1
    assert not (settings.upload_path / second).exists()


def test_nothing_is_swept_when_photos_are_not_stored(no_storage_client, site_id):
    """With storage off there is nothing to delete, and no directory to scan."""
    retention.reset_for_tests()
    _, settings, engine = no_storage_client
    with Session(engine) as session:
        assert retention.sweep_if_due(session, settings) == 0
