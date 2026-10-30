"""Regional intelligence (implemented in Phase 6)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("", summary="List configured regions")
def list_regions() -> None:
    raise not_implemented("Regional intelligence", "Phase 1", planned_for="Phase 6")
