"""Shared pytest fixtures.

Environment is configured *before* the application package is imported so that
settings, engine and Alembic all resolve to the same throwaway SQLite database.
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
def client() -> TestClient:
    app = create_app(get_settings())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def migrated() -> Path:
    """Run the Alembic upgrade once for the whole test session."""
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    command.upgrade(config, "head")
    return _DB_PATH
