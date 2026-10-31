"""Dashboard aggregates.

Phase 4 adds regional rankings and the global heatmap; the summary tiles here are
computed from stored observations so the overview never shows invented numbers.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import AlgorithmRun, FireEvent, FireObservation, ObservationMatch
from app.db.session import get_session
from app.services.data_status import build_data_status

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", summary="Global overview aggregates")
def dashboard_overview(
    start_date: date | None = None,
    end_date: date | None = None,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    stmt = select(
        FireObservation.sensor,
        func.count(),
        func.coalesce(func.sum(FireObservation.frp_mw), 0.0),
    ).group_by(FireObservation.sensor)

    if start_date:
        stmt = stmt.where(
            FireObservation.acquired_at
            >= datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        )
    if end_date:
        stmt = stmt.where(
            FireObservation.acquired_at
            < datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        )

    by_sensor = {
        sensor: {"detections": int(count), "frp_mw": float(frp or 0.0)}
        for sensor, count, frp in session.execute(stmt).all()
    }

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

    return {
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
