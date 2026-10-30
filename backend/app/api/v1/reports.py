"""Report generation and export (implemented in Phase 7)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", summary="List generated reports")
def list_reports() -> None:
    raise not_implemented("Intelligence reports", "Phase 1", planned_for="Phase 7")
