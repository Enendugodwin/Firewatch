"""Background tasks.

Only diagnostics exist in Phase 1. Ingestion, harmonization, anomaly scoring and
report rendering are added in the phases that implement them.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.services.db_health import check_database
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="system.probe_database", bind=True, max_retries=3)
def probe_database(self) -> dict[str, object]:
    """Queue/worker smoke test: probe the database and report it honestly."""
    status = check_database()
    logger.info("worker_db_probe", connected=status.connected, dialect=status.dialect)
    return status.model_dump()


@celery_app.task(name="system.ping")
def ping() -> str:
    return "pong"
