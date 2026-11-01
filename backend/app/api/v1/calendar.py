"""Historical burning calendar: bucketed activity and bucket drill-down."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_session
from app.schemas.calendar import (
    CalendarBucket,
    CalendarDrilldown,
    CalendarMonth,
    CalendarResponse,
)
from app.schemas.observations import ObservationOut
from app.services import calendar as calendar_service
from app.services.anomalies import observed_days
from app.services.observation_queries import (
    BBox,
    ObservationFilters,
    observation_to_dict,
    search_observations,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _filters(
    bbox: str | None,
    sensor: str | None,
    satellite: str | None,
    min_frp: float | None,
    daynight: str | None,
    min_confidence: str | None,
    synthetic: bool | None,
    start_date: date | None = None,
    end_date: date | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> ObservationFilters:
    return ObservationFilters(
        bbox=BBox.parse(bbox) if bbox else None,
        start_date=start_date,
        end_date=end_date,
        start_at=start_at,
        end_at=end_at,
        sensor=sensor,
        satellite=satellite,
        min_frp=min_frp,
        daynight=daynight,
        min_confidence=min_confidence,
        synthetic=synthetic,
    )


@router.get("", response_model=CalendarResponse, summary="Activity buckets for a period")
def calendar_activity(
    start_date: date = Query(..., description="First day of the calendar window (UTC)"),
    end_date: date = Query(..., description="Last day of the calendar window (UTC)"),
    granularity: str = Query("day", description="day, week, month or year"),
    start_at: datetime | None = Query(
        None, description="Exact start (ISO 8601, UTC), inclusive"
    ),
    end_at: datetime | None = Query(None, description="Exact end (ISO 8601, UTC), exclusive"),
    bbox: str | None = Query(None, description="west,south,east,north"),
    sensor: str | None = Query(None, description="MODIS or VIIRS"),
    satellite: str | None = None,
    min_frp: float | None = Query(None, ge=0),
    daynight: str | None = Query(None, pattern="^[DdNn]$"),
    min_confidence: str | None = Query(None, pattern="^(?i)(low|nominal|high)$"),
    synthetic: bool | None = Query(None, description="Filter labelled fixture data"),
    session: Session = Depends(get_session),
) -> CalendarResponse:
    parsed_granularity = calendar_service.parse_granularity(granularity)
    filters = _filters(
        bbox,
        sensor,
        satellite,
        min_frp,
        daynight,
        min_confidence,
        synthetic,
        start_date,
        end_date,
        start_at,
        end_at,
    )
    result = calendar_service.calendar_activity(
        session,
        filters,
        start=start_date,
        end=end_date,
        granularity=parsed_granularity,
    )
    return CalendarResponse(**result)


@router.get(
    "/months",
    response_model=list[CalendarMonth],
    summary="Months that hold data, for the calendar month picker",
)
def calendar_months(
    start_date: date = Query(..., description="First day of the search window (UTC)"),
    end_date: date = Query(..., description="Last day of the search window (UTC)"),
    synthetic: bool | None = Query(None, description="Filter labelled fixture data"),
    session: Session = Depends(get_session),
) -> list[CalendarMonth]:
    """
    Group the stored days by month so the UI can offer only months that exist,
    with their totals and how many days a source actually observed.
    """
    calendar_service.validate_span(start_date, end_date)
    filters = _filters(None, None, None, None, None, None, synthetic, start_date, end_date)
    daily = calendar_service.daily_metrics(session, filters)
    observed = observed_days(session, start_date, end_date, None)

    months: dict[str, CalendarMonth] = {}
    for day, metrics in daily.items():
        key = day.strftime("%Y-%m")
        start = day.replace(day=1)
        end = calendar_service.bucket_for(start, "month").end
        entry = months.get(key)
        if entry is None:
            entry = CalendarMonth(
                month=key,
                start=start,
                end=end,
                detections=0,
                active_days=0,
                observed_days=0,
            )
            months[key] = entry
        entry.detections += int(metrics.get("detections", 0))
        entry.active_days += 1

    for day in observed:
        key = day.strftime("%Y-%m")
        entry = months.get(key)
        if entry is not None:
            entry.observed_days += 1

    return sorted(months.values(), key=lambda item: item.month)


def _bucket_payload(
    session: Session,
    filters: ObservationFilters,
    *,
    bucket_start: date,
    granularity: str,
    sensor: str | None,
) -> dict[str, Any]:
    parsed_granularity = calendar_service.parse_granularity(granularity)
    bucket = calendar_service.bucket_for(bucket_start, parsed_granularity)
    result = calendar_service.calendar_activity(
        session,
        filters,
        start=bucket.start,
        end=bucket.end,
        granularity=parsed_granularity,
    )
    if not result["buckets"]:
        raise AppError("not_found", "No bucket covers that date.")
    return result["buckets"][0]


@router.get(
    "/drilldown",
    response_model=CalendarDrilldown,
    summary="Observations behind one calendar bucket",
)
def calendar_drilldown(
    bucket_start: date = Query(..., description="Any date inside the bucket"),
    granularity: str = Query("day", description="day, week, month or year"),
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    bbox: str | None = None,
    sensor: str | None = None,
    satellite: str | None = None,
    min_frp: float | None = Query(None, ge=0),
    daynight: str | None = Query(None, pattern="^[DdNn]$"),
    min_confidence: str | None = Query(None, pattern="^(?i)(low|nominal|high)$"),
    synthetic: bool | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> CalendarDrilldown:
    parsed_granularity = calendar_service.parse_granularity(granularity)
    bucket = calendar_service.bucket_for(bucket_start, parsed_granularity)

    aggregate_filters = _filters(
        bbox,
        sensor,
        satellite,
        min_frp,
        daynight,
        min_confidence,
        synthetic,
        bucket.start,
        bucket.end,
        start_at,
        end_at,
    )
    summary = _bucket_payload(
        session,
        aggregate_filters,
        bucket_start=bucket_start,
        granularity=granularity,
        sensor=sensor,
    )

    rows, total = search_observations(
        session, aggregate_filters, limit=limit, offset=offset
    )
    return CalendarDrilldown(
        bucket=CalendarBucket(**summary),
        total=total,
        returned=len(rows),
        limit=limit,
        items=[ObservationOut(**observation_to_dict(row)) for row in rows],
    )
