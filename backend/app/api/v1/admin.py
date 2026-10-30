"""Administration and ingestion control (implemented in Phase 2)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ingestion/jobs", summary="Ingestion job history")
def ingestion_jobs() -> None:
    raise not_implemented("Ingestion administration", "Phase 1", planned_for="Phase 2")
