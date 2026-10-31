"""Historical burning activity calendar (implemented in Phase 5)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("", summary="Calendar activity for a region and period")
def calendar_activity() -> None:
    raise not_implemented("Burning calendar", planned_for="Phase 5")
