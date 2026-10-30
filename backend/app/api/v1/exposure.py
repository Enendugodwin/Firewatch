"""Exposure screening (implemented in Phase 6)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/exposure", tags=["exposure"])


@router.get("", summary="Exposure screening summary")
def exposure_summary() -> None:
    raise not_implemented("Exposure analysis", "Phase 1", planned_for="Phase 6")
