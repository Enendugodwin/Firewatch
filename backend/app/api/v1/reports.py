"""Reports: a briefing snapshot and its export formats."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_session
from app.services.calendar import validate_span
from app.services.observation_queries import BBox, ObservationFilters
from app.services.reports import build_report, report_markdown

router = APIRouter(prefix="/reports", tags=["reports"])


def _filters(
    bbox: str | None,
    start: date,
    end: date,
    synthetic: bool | None = None,
) -> ObservationFilters:
    if start > end:
        raise AppError(
            "bad_request",
            "start_date must be on or before end_date.",
            details={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
    validate_span(start, end)
    return ObservationFilters(
        bbox=BBox.parse(bbox) if bbox else None,
        start_date=start,
        end_date=end,
        synthetic=synthetic,
    )


@router.get("", summary="Report capabilities and formats")
def reports_index() -> dict[str, object]:
    return {
        "formats": ["json", "markdown"],
        "endpoints": [
            "/api/v1/reports/summary?start_date=&end_date=",
            "/api/v1/reports/export?format=markdown&start_date=&end_date=",
        ],
        "note": "Reports are generated from the database; no narrative is model-written.",
    }


@router.get("/summary", summary="Report for a period")
def report_summary(
    start_date: date = Query(..., description="First day (UTC)"),
    end_date: date = Query(..., description="Last day (UTC)"),
    bbox: str | None = Query(None, description="west,south,east,north"),
    synthetic: bool | None = Query(None, description="Filter labelled fixture data"),
    top: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    filters = _filters(bbox, start_date, end_date, synthetic)
    return build_report(session, filters, start=start_date, end=end_date, top=top)


@router.get("/export", summary="Download the report as Markdown or JSON")
def report_export(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    bbox: str | None = None,
    synthetic: bool | None = None,
    top: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> Response:
    filters = _filters(bbox, start_date, end_date, synthetic)
    report = build_report(session, filters, start=start_date, end=end_date, top=top)

    if format == "json":
        body = json.dumps(report, indent=2, default=str)
        media = "application/json"
        filename = f"firewatch-report-{start_date}-{end_date}.json"
    else:
        body = report_markdown(report)
        media = "text/markdown; charset=utf-8"
        filename = f"firewatch-report-{start_date}-{end_date}.md"

    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
