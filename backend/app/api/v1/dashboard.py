"""Dashboard aggregates.

Phase 4 adds regional rankings and the global heatmap; the summary tiles here are
computed from stored observations so the overview never shows invented numbers.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import MISS, TTLCache
from app.core.config import Settings, get_settings
from app.db.models import AlgorithmRun, FireEvent, ObservationMatch
from app.db.session import get_session
from app.services import rollups
from app.services.data_status import build_data_status
from app.services.observation_queries import ObservationFilters

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

#: The overview polls; identical windows reuse a short-lived response.
_DASHBOARD_CACHE = TTLCache(ttl_seconds=15, max_entries=32, name="dashboard")


@router.get("", summary="Global overview aggregates")
def dashboard_overview(
    start_date: date | None = None,
    end_date: date | None = None,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    cache_key = f"{start_date}:{end_date}"
    cached = _DASHBOARD_CACHE.get(cache_key)
    if cached is not MISS:
        return cached

    # The daily rollup answers the date-only totals; the live scan stays as the
    # fallback when a rollup is unavailable (SQLite) or the filters widen.
    by_sensor: dict[str, dict[str, float]] = {}
    filters = ObservationFilters(start_date=start_date, end_date=end_date)
    for row in rollups.activity_rows(session, filters):
        bucket = by_sensor.setdefault(
            row.sensor, {"detections": 0.0, "frp_mw": 0.0}
        )
        bucket["detections"] += int(row.detections or 0)
        bucket["frp_mw"] += float(row.frp_sum_mw or 0.0)

    matches = dict(
        session.execute(
            select(ObservationMatch.match_status, func.count()).group_by(
                ObservationMatch.match_status
            )
        ).all()
    )
    events = session.scalar(select(func.count()).select_from(FireEvent)) or 0
    last_run = session.scalars(
        select(AlgorithmRun)
        .where(AlgorithmRun.kind == "harmonization")
        .order_by(AlgorithmRun.started_at.desc())
        .limit(1)
    ).first()
    scope = (last_run.parameters or {}).get("scope") if last_run else None
    data = build_data_status(session, settings)

    payload: dict[str, object] = {
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "detections": {
            "total": sum(item["detections"] for item in by_sensor.values()),
            "modis": by_sensor.get("MODIS", {}).get("detections", 0),
            "viirs": by_sensor.get("VIIRS", {}).get("detections", 0),
            "frp_mw": sum(item["frp_mw"] for item in by_sensor.values()),
        },
        "matches": {
            "total": int(sum(matches.values())),
            "probable": int(matches.get("probable", 0)),
            "possible": int(matches.get("possible", 0)),
        },
        "events": int(events),
        "scope": scope,
        "data": data.model_dump(),
        "note": (
            "Counts are satellite thermal detections, not the number of fires. "
            "FRP sums are reported in MW."
        ),
    }
    _DASHBOARD_CACHE.set(cache_key, payload)
    return payload
