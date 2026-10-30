"""MODIS–VIIRS harmonization (implemented in Phase 3)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/harmonization", tags=["harmonization"])


@router.get("/summary", summary="Cross-sensor harmonization statistics")
def harmonization_summary() -> None:
    raise not_implemented("Harmonization summary", "Phase 1", planned_for="Phase 3")


@router.get("/matches", summary="Probable cross-sensor matches")
def harmonization_matches() -> None:
    raise not_implemented("Cross-sensor matches", "Phase 1", planned_for="Phase 3")
