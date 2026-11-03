"""Shared pytest fixtures.

Environment is configured *before* the application package is imported so that
settings, engine and Alembic all resolve to the same throwaway SQLite database.
Observation tables are emptied before every test; the data-source registry is
kept so tests exercise the real seeded catalogue.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP_DIR = Path(tempfile.mkdtemp(prefix="firewatch-tests-"))
_DB_PATH = _TMP_DIR / "test.db"

os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite+pysqlite:///{_DB_PATH.as_posix()}",
        "LOG_JSON": "false",
        "LOG_LEVEL": "WARNING",
        "FIRMS_MAP_KEY": "",
        "CORS_ORIGINS": "http://localhost:5273",
    }
)

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def db_path() -> Path:
    return _DB_PATH


@pytest.fixture(scope="session")
def migrated() -> Path:
    """Apply the full migration chain once for the session."""
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    command.upgrade(config, "head")

    from scripts.seed_sources import seed

    seed()
    return _DB_PATH


OBSERVATION_TABLES = (
    "event_observations",
    "fire_events",
    "observation_matches",
    "fire_observations",
    "raw_observations",
    "source_availability",
    "ingestion_partitions",
    "ingestion_runs",
    "algorithm_runs",
    "harmonization_coverage",
    "watched_assets",
)


@pytest.fixture(autouse=True)
def clean_db(migrated: Path) -> None:
    """Empty observation tables between tests so assertions stay isolated."""
    from sqlalchemy import func, select, text

    from app.db.models import DataSource
    from app.db.session import get_engine, session_scope

    engine = get_engine()
    with engine.begin() as connection:
        for table in OBSERVATION_TABLES:
            connection.execute(text(f"DELETE FROM {table}"))  # noqa: S608 - fixed names

    # A downgrade/upgrade cycle in the migration tests empties the registry; the
    # catalogue is part of the baseline every other test relies on.
    with session_scope() as session:
        registered = session.scalar(select(func.count()).select_from(DataSource)) or 0
    if registered == 0:
        from scripts.seed_sources import seed

        seed()


@pytest.fixture(scope="session")
def client(migrated: Path) -> TestClient:
    app = create_app(get_settings())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def loaded_fixture(client: TestClient) -> dict[str, int]:
    """Load the labelled synthetic fixture and run harmonization + events."""
    from app.services import events as events_service
    from app.services import harmonization as harmonization_service
    from app.services.ingestion import ingest_csv_text

    fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "firms_sample"
    from scripts.ingest_fixture import FIXTURES, _dates

    inserted = 0
    for source_code, filename in FIXTURES:
        text = (fixtures / filename).read_text(encoding="utf-8")
        start, end = _dates(text)
        result = ingest_csv_text(
            source_code, text, start_date=start, end_date=end, is_synthetic=True
        )
        inserted += result.records_inserted

    harmonization = harmonization_service.run_harmonization(is_synthetic=True)
    events = events_service.run_event_clustering(is_synthetic=True)
    return {
        "inserted": inserted,
        "probable": harmonization["probable"],
        "possible": harmonization["possible"],
        "events": events["events"],
    }
