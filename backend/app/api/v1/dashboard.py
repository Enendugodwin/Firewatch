"""Dashboard aggregates (implemented in Phase 4)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", summary="Global overview aggregates")
def dashboard_overview() -> None:
    raise not_implemented("Dashboard overview", "Phase 1", planned_for="Phase 4")
