"""Regional intelligence over approximate country boxes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_session
from app.services.calendar import validate_span
from app.services.observation_queries import ObservationFilters
from app.services.regions import regional_profiles

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("", summary="Regional profiles for a period")
def list_regions(
    start_date: date = Query(..., description="First day (UTC)"),
    end_date: date = Query(..., description="Last day (UTC)"),
    limit: int = Query(10, ge=1, le=50),
    names: str | None = Query(None, description="Comma-separated country names"),
    synthetic: bool | None = Query(None, description="Filter labelled fixture data"),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    if start_date > end_date:
        raise AppError(
            "bad_request",
            "start_date must be on or before end_date.",
            details={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )
    validate_span(start_date, end_date)

    filters = ObservationFilters(
        start_date=start_date, end_date=end_date, synthetic=synthetic
    )
    wanted = [piece.strip() for piece in names.split(",")] if names else None
    return regional_profiles(session, filters, limit=limit, names=wanted)
