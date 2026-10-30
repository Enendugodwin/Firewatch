"""Configuration parsing and derived flags."""

from __future__ import annotations

from app.core.config import Settings


def test_cors_origins_accept_comma_separated_values() -> None:
    settings = Settings(cors_origins="http://a.test, http://b.test", _env_file=None)  # type: ignore[call-arg]

    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_origins_accept_a_list() -> None:
    settings = Settings(cors_origins=["http://a.test"], _env_file=None)  # type: ignore[call-arg]

    assert settings.cors_origins == ["http://a.test"]


def test_postgres_flags() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://u:p@localhost:5432/firewatch", _env_file=None
    )  # type: ignore[call-arg]

    assert settings.is_postgres is True
    assert settings.is_sqlite is False
    assert settings.database_dialect == "postgresql"


def test_sqlite_flags() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///./x.db", _env_file=None)  # type: ignore[call-arg]

    assert settings.is_sqlite is True
    assert settings.is_postgres is False


def test_secrets_are_considered_absent_when_blank() -> None:
    settings = Settings(firms_map_key="", ai_provider=None, _env_file=None)  # type: ignore[call-arg]

    assert settings.firms_configured is False
    assert settings.ai_configured is False


def test_secrets_are_considered_present_when_supplied() -> None:
    settings = Settings(
        firms_map_key="abc123",
        ai_provider="openai",
        ai_api_key="k",
        ai_model="m",
        _env_file=None,
    )  # type: ignore[call-arg]

    assert settings.firms_configured is True
    assert settings.ai_configured is True
