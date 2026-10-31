"""Celery application for ingestion, harmonization and report jobs.

Phase 1 defines the worker so the deployment surface is real and testable; the
ingestion tasks themselves land in Phase 2.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()

celery_app = Celery(
    "firewatch",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
)


@celery_app.on_after_configure.connect
def _configure_signal_logging(**_kwargs: object) -> None:
    configure_logging(level=settings.log_level, json_output=settings.log_json)
    get_logger("app.workers").info("worker_configured", broker=settings.redis_url.split("@")[-1])
