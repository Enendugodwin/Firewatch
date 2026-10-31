"""Availability sync: coverage windows must not turn gaps into quiet days."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.db.models import SourceAvailability
from app.db.session import session_scope
from app.services.firms.client import AvailabilityWindow
from app.services.ingestion import sync_availability


class StubClient:
    def __init__(self, window: AvailabilityWindow) -> None:
        self.window = window

    def fetch_availability(self, source_code: str) -> AvailabilityWindow:
        return self.window


def test_dates_inside_coverage_are_observed_days() -> None:
    stub = StubClient(
        AvailabilityWindow(
            source_code="MODIS_SP",
            min_date=date(2026, 8, 1),
            max_date=date(2026, 10, 30),
        )
    )

    result = sync_availability(
        "MODIS_SP",
        start_date=date(2026, 10, 28),
        end_date=date(2026, 10, 30),
        client=stub,  # type: ignore[arg-type]
    )

    assert result["counts"] == {"available": 3}
    assert result["coverage"]["max_date"] == "2026-10-30"

    with session_scope() as session:
        rows = session.scalars(select(SourceAvailability)).all()
        assert [row.status for row in rows] == ["available", "available", "available"]


def test_dates_outside_coverage_are_labelled_not_silently_zero() -> None:
    stub = StubClient(
        AvailabilityWindow(
            source_code="MODIS_SP",
            min_date=date(2026, 8, 1),
            max_date=date(2026, 10, 30),
        )
    )

    result = sync_availability(
        "MODIS_SP",
        start_date=date(2026, 7, 30),
        end_date=date(2026, 11, 1),
        client=stub,  # type: ignore[arg-type]
    )

    assert result["counts"] == {
        "before_coverage": 2,
        "available": 91,
        "not_yet_available": 2,
    }

    with session_scope() as session:
        statuses = {
            row.observation_date.isoformat(): row.status
            for row in session.scalars(select(SourceAvailability)).all()
        }

    assert statuses["2026-07-31"] == "before_coverage"
    assert statuses["2026-08-01"] == "available"
    assert statuses["2026-11-01"] == "not_yet_available"
