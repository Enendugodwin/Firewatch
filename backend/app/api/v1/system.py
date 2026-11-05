"""System status, module registry and data-source endpoints."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.modules import MODULES
from app.core.runtime import STARTED_AT, current_phase
from app.db.models import DataSource, FireObservation
from app.db.session import get_session
from app.schemas.system import (
    CapabilityStatus,
    DataStatus,
    ModuleStatusItem,
    SourceOut,
    SystemStatus,
)
from app.services.data_status import build_data_status
from app.services.db_health import check_database
from app.services.sources import FIRMS_SOURCES

router = APIRouter(prefix="/system", tags=["system"])


def empty_data_status(settings: Settings, reason: str) -> DataStatus:
    return DataStatus(
        freshness="no_data",
        freshness_reason=reason,
        firms_configured=settings.firms_configured,
        sources_registered=len(FIRMS_SOURCES),
        observations_stored=None,
    )


@router.get("/status", response_model=SystemStatus, summary="Application status")
def system_status(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> SystemStatus:
    phase, phase_name = current_phase()
    database = check_database(settings)

    if database.connected:
        try:
            data = build_data_status(session, settings)
        except SQLAlchemyError:
            data = empty_data_status(
                settings,
                "The observation tables are not present yet. Run `alembic upgrade head`.",
            )
    else:
        data = empty_data_status(settings, "The database is unreachable, so data state is unknown.")

    return SystemStatus(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        phase=phase,
        phase_name=phase_name,
        server_time=datetime.now(UTC),
        uptime_seconds=round(time.monotonic() - STARTED_AT, 2),
        database=database,
        data=data,
        capabilities=CapabilityStatus(
            authentication=True,
            rate_limiting=True,
            ai_assistant=True,
            reports=True,
            ingestion=settings.firms_configured,
            spatial=settings.is_postgres,
        ),
        modules=[ModuleStatusItem(**module) for module in MODULES],
    )


@router.get(
    "/modules",
    response_model=list[ModuleStatusItem],
    summary="Module registry and implementation status",
)
def list_modules() -> list[ModuleStatusItem]:
    return [ModuleStatusItem(**module) for module in MODULES]


@router.get(
    "/sources",
    response_model=list[SourceOut],
    summary="Registered NASA FIRMS products",
)
def list_sources(session: Session = Depends(get_session)) -> list[SourceOut]:
    try:
        registered = {row.source_code for row in session.query(DataSource).all()}
        counts: dict[str, tuple[int, datetime | None]] = {}
        rows = session.execute(
            select(
                FireObservation.source_code,
                func.count(),
                func.max(FireObservation.acquired_at),
            ).group_by(FireObservation.source_code)
        ).all()
        for code, count, latest in rows:
            counts[str(code)] = (int(count), latest)
    except SQLAlchemyError as exc:
        raise AppError(
            "unavailable",
            "The data-source registry is not available. Run migrations and seed the registry.",
            details={"hint": "alembic upgrade head && python -m scripts.seed_sources"},
        ) from exc

    payload: list[SourceOut] = []
    for source in FIRMS_SOURCES:
        observations, last_seen = counts.get(source.code, (0, None))
        payload.append(
            SourceOut(
                **source.__dict__,
                status="ok"
                if observations
                else ("not_ingested" if source.code in registered else "error"),
                observations=observations,
                last_observation_at=last_seen,
            )
        )
    return payload
