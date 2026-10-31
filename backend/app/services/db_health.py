"""Database health and capability probing."""

from __future__ import annotations

import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.session import get_engine
from app.schemas.system import DatabaseStatus

logger = get_logger(__name__)


def check_database(settings: Settings | None = None) -> DatabaseStatus:
    """Probe the database without raising: readiness reports, never crashes."""
    settings = settings or get_settings()
    started = time.perf_counter()
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            postgis: bool | None = None
            if settings.is_postgres:
                try:
                    postgis = (
                        connection.execute(text("SELECT PostGIS_Version()")).scalar_one_or_none()
                        is not None
                    )
                except SQLAlchemyError:
                    postgis = False
            return DatabaseStatus(
                dialect=settings.database_dialect,
                connected=True,
                postgis=postgis,
                latency_ms=latency_ms,
            )
    except Exception as exc:  # noqa: BLE001 - surfaced to /ready, not swallowed
        logger.warning("database_probe_failed", error=str(exc))
        return DatabaseStatus(
            dialect=settings.database_dialect,
            connected=False,
            postgis=None,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            error=str(exc).splitlines()[0][:300],
        )
