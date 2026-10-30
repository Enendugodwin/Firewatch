"""Observation search and map feeds (implemented in Phase 2/4)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/fires", tags=["fires"])


@router.get("", summary="Search fire observations")
def search_fires() -> None:
    raise not_implemented("Observation search", "Phase 1", planned_for="Phase 2")


@router.get("/geojson", summary="Map-ready observation GeoJSON")
def fires_geojson() -> None:
    raise not_implemented("Observation GeoJSON feed", "Phase 1", planned_for="Phase 4")
