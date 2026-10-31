"""Version 1 API surface.

Route groups mirror the specification exactly so that each delivery phase fills
in a known contract rather than inventing shapes later. Endpoints whose module
is not built yet return ``501 not_implemented`` with the phase that will build
them — never sample data.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    anomalies,
    assistant,
    auth,
    calendar,
    dashboard,
    exposure,
    fires,
    geo,
    harmonization,
    regions,
    reports,
    system,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(dashboard.router)
api_router.include_router(fires.router)
api_router.include_router(geo.router)
api_router.include_router(calendar.router)
api_router.include_router(harmonization.router)
api_router.include_router(anomalies.router)
api_router.include_router(regions.router)
api_router.include_router(exposure.router)
api_router.include_router(reports.router)
api_router.include_router(assistant.router)
api_router.include_router(admin.router)
api_router.include_router(auth.router)

__all__ = ["api_router"]
