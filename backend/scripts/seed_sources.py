"""Seed the NASA FIRMS data-source registry.

Idempotent: re-running updates metadata without creating duplicates, so it is
safe in development, CI and production bootstrap.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.db.models import DataSource
from app.db.session import session_scope
from app.services.sources import FIRMS_SOURCES

logger = get_logger("scripts.seed_sources")


def seed() -> int:
    """Insert or update every registered source. Returns the number touched."""
    touched = 0
    with session_scope() as session:
        existing = {
            source.source_code: source for source in session.scalars(select(DataSource)).all()
        }
        for definition in FIRMS_SOURCES:
            row = existing.get(definition.code)
            if row is None:
                session.add(
                    DataSource(
                        source_code=definition.code,
                        sensor=definition.sensor,
                        satellite=definition.satellite,
                        processing_level=definition.processing_level,
                        description=definition.description,
                        active=True,
                    )
                )
            else:
                row.sensor = definition.sensor
                row.satellite = definition.satellite
                row.processing_level = definition.processing_level
                row.description = definition.description
            touched += 1
    logger.info("sources_seeded", count=touched)
    return touched


if __name__ == "__main__":
    configure_logging(json_output=False)
    seed()
