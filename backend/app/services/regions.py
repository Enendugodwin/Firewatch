"""Regional intelligence, honest about what it is.

There are no administrative boundary polygons in this deployment, so a "region"
is the approximate centroid box of a country from the offline gazetteer. That is
enough to rank activity and frame a map, and it is labelled as approximate in
every response. It is never presented as a country boundary.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FireObservation
from app.services.gazetteer import COUNTRIES, Place
from app.services.observation_queries import BBox, ObservationFilters

REGION_NOTE = (
    "Regions are approximate centroid boxes from the offline gazetteer, not "
    "administrative boundaries. Neighbouring countries can overlap."
)


def region_box(place: Place, half_degrees: float = 6.0) -> BBox:
    west = max(-180.0, place.longitude - half_degrees)
    east = min(180.0, place.longitude + half_degrees)
    south = max(-85.0, place.latitude - half_degrees)
    north = min(85.0, place.latitude + half_degrees)
    return BBox(west, south, east, north)


def _stats(session: Session, filters: ObservationFilters, box: BBox) -> dict[str, Any]:
    scoped = ObservationFilters(
        bbox=box,
        start_date=filters.start_date,
        end_date=filters.end_date,
        start_at=filters.start_at,
        end_at=filters.end_at,
        sensor=filters.sensor,
        satellite=filters.satellite,
        min_frp=filters.min_frp,
        daynight=filters.daynight,
        min_confidence=filters.min_confidence,
        synthetic=filters.synthetic,
    )
    statement = scoped.apply(
        select(
            func.count(),
            func.sum(FireObservation.frp_mw),
            func.max(FireObservation.frp_mw),
            func.count(func.distinct(func.date(FireObservation.acquired_at))),
        )
    )
    count, frp_sum, frp_max, days = session.execute(statement).one()
    return {
        "detections": int(count or 0),
        "frp_sum_mw": round(float(frp_sum or 0.0), 2),
        "frp_max_mw": round(float(frp_max), 2) if frp_max is not None else None,
        "active_days": int(days or 0),
    }


def regional_profiles(
    session: Session,
    filters: ObservationFilters,
    *,
    limit: int = 10,
    names: list[str] | None = None,
) -> dict[str, Any]:
    wanted = {name.lower() for name in names} if names else None
    profiles = []
    for place in COUNTRIES:
        if wanted is not None and place.name.lower() not in wanted:
            continue
        box = region_box(place)
        stats = _stats(session, filters, box)
        profiles.append(
            {
                "name": place.name,
                "iso": place.iso,
                "kind": place.kind,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "bbox": box.as_list(),
                **stats,
            }
        )

    profiles.sort(key=lambda item: item["detections"], reverse=True)
    return {
        "regions": profiles[:limit],
        "note": REGION_NOTE,
        "half_degrees": 6.0,
    }
