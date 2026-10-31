"""Data freshness and storage state.

Freshness is derived from stored observations and recorded ingestion runs — never
from page refreshes. Missing data is reported as unknown or stale, never as zero
activity.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    FireObservation,
    IngestionRun,
    SourceAvailability,
)
from app.schemas.system import DataStatus

#: FIRMS NRT typically lags a few hours; standard processing lags days.
CURRENT_THRESHOLD = timedelta(hours=6)
DELAYED_THRESHOLD = timedelta(hours=48)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite drops timezone info; treat stored values as UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _freshness(age: timedelta | None) -> tuple[str, str]:
    if age is None:
        return "no_data", "No observations are stored yet."
    if age <= CURRENT_THRESHOLD:
        return "current", "Latest observation is within the current window."
    if age <= DELAYED_THRESHOLD:
        return "delayed", "Latest observation is older than the current window."
    return "stale", "Latest observation is more than 48 hours old."


def build_data_status(session: Session, settings: Settings) -> DataStatus:
    total = session.scalar(select(func.count()).select_from(FireObservation)) or 0
    synthetic = (
        session.scalar(
            select(func.count())
            .select_from(FireObservation)
            .where(FireObservation.is_synthetic.is_(True))
        )
        or 0
    )
    latest = _aware(session.scalar(select(func.max(FireObservation.acquired_at))))
    last_run_at = _aware(
        session.scalar(
            select(func.max(IngestionRun.completed_at)).where(
                IngestionRun.status.in_(("succeeded", "partial"))
            )
        )
    )
    last_run_started = _aware(
        session.scalar(
            select(func.max(IngestionRun.started_at)).where(
                IngestionRun.status.in_(("succeeded", "partial"))
            )
        )
    )

    age = None
    if latest is not None:
        age = datetime.now(UTC) - latest
    freshness, reason = _freshness(age)

    if total == 0:
        if not settings.firms_configured:
            reason = (
                "FIRMS_MAP_KEY is not configured, so no NASA observations can be retrieved. "
                "Values shown elsewhere are placeholders only."
            )
        elif last_run_at is not None:
            reason = (
                "Ingestion has run but stored no observations for the requested period. "
                "That may be a genuinely quiet window or a data gap."
            )
        else:
            reason = (
                "A FIRMS MAP_KEY is configured but no ingestion has run yet. "
                "Trigger one from Settings or scripts/ingest_recent.py."
            )
    elif synthetic == total:
        reason = (
            "All stored observations come from the labelled synthetic fixture "
            "(not NASA data). They exercise the pipeline only."
        )
        if freshness == "current":
            freshness = "current"

    missing_dates = (
        session.scalar(
            select(func.count())
            .select_from(SourceAvailability)
            .where(SourceAvailability.status == "missing")
        )
        or 0
    )

    return DataStatus(
        freshness=freshness,  # type: ignore[arg-type]
        freshness_reason=reason,
        firms_configured=settings.firms_configured,
        sources_registered=len(_registered_count(session)),
        observations_stored=total,
        synthetic_observations=synthetic,
        missing_dates=missing_dates,
        last_ingested_at=last_run_at or last_run_started,
        last_observation_at=latest,
    )


def _registered_count(session: Session) -> list:
    from app.db.models import DataSource

    return list(session.scalars(select(DataSource.source_code)).all())
