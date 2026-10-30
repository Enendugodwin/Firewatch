"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.schemas.common import HealthResponse
from app.services.db_health import check_database

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok", service=settings.app_name, version=settings.app_version
    )


@router.get("/ready", summary="Readiness probe (checks the database)")
def ready(
    response: Response, settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    database = check_database(settings)
    if not database.connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unavailable",
            "database": database.model_dump(),
            "detail": "Database is not reachable; analytical endpoints cannot serve.",
        }
    return {"status": "ready", "database": database.model_dump()}
