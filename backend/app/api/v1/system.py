"""System status, module registry and data-source endpoints."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.modules import MODULES
from app.core.runtime import STARTED_AT, current_phase
from app.schemas.system import (
    CapabilityStatus,
    DataStatus,
    ModuleStatusItem,
    SourceOut,
    SystemStatus,
)
from app.services.db_health import check_database
from app.services.sources import FIRMS_SOURCES

router = APIRouter(prefix="/system", tags=["system"])


def build_data_status(settings: Settings) -> DataStatus:
    """Describe data state without pretending anything has been ingested."""
    if not settings.firms_configured:
        reason = (
            "FIRMS_MAP_KEY is not configured, so no NASA observations can be "
            "retrieved. Values shown elsewhere are placeholders only."
        )
    else:
        reason = (
            "A FIRMS MAP_KEY is configured but no ingestion has run yet "
            "(ingestion ships in Phase 2)."
        )
    return DataStatus(
        freshness="no_data",
        freshness_reason=reason,
        firms_configured=settings.firms_configured,
        sources_registered=len(FIRMS_SOURCES),
        observations_stored=None,
        last_ingested_at=None,
        last_observation_at=None,
    )


@router.get("/status", response_model=SystemStatus, summary="Application status")
def system_status(settings: Settings = Depends(get_settings)) -> SystemStatus:
    phase, phase_name = current_phase()
    return SystemStatus(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        phase=phase,
        phase_name=phase_name,
        server_time=datetime.now(UTC),
        uptime_seconds=round(time.monotonic() - STARTED_AT, 2),
        database=check_database(settings),
        data=build_data_status(settings),
        capabilities=CapabilityStatus(
            authentication=False,
            rate_limiting=False,
            ai_assistant=settings.ai_configured,
            reports=False,
            ingestion=False,
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
def list_sources() -> list[SourceOut]:
    return [SourceOut(**source.__dict__, status="not_ingested") for source in FIRMS_SOURCES]
