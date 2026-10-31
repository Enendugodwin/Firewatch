"""Map navigation search (offline gazetteer)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.gazetteer import search

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/search", summary="Search countries, cities or a coordinate pair")
def geo_search(
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(8, ge=1, le=20),
) -> dict[str, object]:
    """
    Offline search over approximate centroids plus ``lat,lon`` parsing.

    Results are navigation aids for the map; they are not authoritative
    boundaries or place names.
    """
    results = search(q, limit=limit)
    return {
        "query": q,
        "count": len(results),
        "results": [place.as_dict() for place in results],
        "note": "Approximate centroids for map navigation; coordinate pairs are accepted.",
    }
