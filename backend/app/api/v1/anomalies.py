"""Anomaly detection (implemented in Phase 6)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("", summary="Search detected anomalies")
def list_anomalies() -> None:
    raise not_implemented("Anomaly detection", planned_for="Phase 6")
