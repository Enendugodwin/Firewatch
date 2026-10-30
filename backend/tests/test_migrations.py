"""Migrations and the idempotent source seed.

These run against SQLite in CI (PostgreSQL/PostGIS in the Docker workflow). The
PostGIS extension statement is PostgreSQL-only by design, so the same revision
applies to both.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text

from app.db.session import get_engine, session_scope
from scripts.seed_sources import seed


def test_migration_creates_the_source_registry(migrated: Path) -> None:
    tables = inspect(get_engine()).get_table_names()

    assert "data_sources" in tables
    assert "alembic_version" in tables


def test_migration_is_applied_once(migrated: Path) -> None:
    with get_engine().connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == "0001_foundation"


def test_seed_is_idempotent(migrated: Path) -> None:
    assert seed() == 8
    assert seed() == 8

    with session_scope() as session:
        rows = session.execute(
            text("SELECT source_code, sensor FROM data_sources ORDER BY source_code")
        ).all()

    assert len(rows) == 8
    assert {row.source_code for row in rows} == {
        "MODIS_SP",
        "VIIRS_SNPP_SP",
        "VIIRS_NOAA20_SP",
        "VIIRS_NOAA21_SP",
        "MODIS_NRT",
        "VIIRS_SNPP_NRT",
        "VIIRS_NOAA20_NRT",
        "VIIRS_NOAA21_NRT",
    }
    modis = [row for row in rows if row.sensor == "MODIS"]
    assert len(modis) == 2


def test_downgrade_removes_registry(migrated: Path) -> None:
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))

    command.downgrade(config, "base")
    assert "data_sources" not in inspect(get_engine()).get_table_names()

    command.upgrade(config, "head")
    assert "data_sources" in inspect(get_engine()).get_table_names()
