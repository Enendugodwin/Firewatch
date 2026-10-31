"""Historical burning calendar: buckets, coverage states and drill-down."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import DataSource, SourceAvailability
from app.db.session import session_scope
from app.services.calendar import bucket_for, buckets_between, validate_span


def _range(start: str = "2026-10-26", end: str = "2026-10-31") -> dict[str, str]:
    return {"start_date": start, "end_date": end, "granularity": "day"}


def _record_availability(source_code: str, days: list[tuple[str, str]]) -> None:
    with session_scope() as session:
        source = session.scalar(select(DataSource).where(DataSource.source_code == source_code))
        assert source is not None
        for day, status in days:
            parsed = date.fromisoformat(day)
            existing = session.scalar(
                select(SourceAvailability).where(
                    SourceAvailability.source_id == source.id,
                    SourceAvailability.observation_date == parsed,
                )
            )
            if existing:
                existing.status = status
            else:
                session.add(
                    SourceAvailability(
                        source_id=source.id, observation_date=parsed, status=status
                    )
                )


def test_calendar_returns_every_day_including_empty_ones(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/calendar", params={**_range(), "synthetic": "true"}
    ).json()

    assert body["granularity"] == "day"
    assert body["start_date"] == "2026-10-26"
    assert body["end_date"] == "2026-10-31"
    assert len(body["buckets"]) == 6

    days = [bucket["start"] for bucket in body["buckets"]]
    assert days == [
        "2026-10-26",
        "2026-10-27",
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
        "2026-10-31",
    ]

    total = sum(bucket["detections"] for bucket in body["buckets"])
    assert total == loaded_fixture["inserted"]
    assert body["totals"]["detections"] == total
    assert body["totals"]["buckets"] == 6


def test_calendar_metrics_are_independent_and_reconcile(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/calendar",
        params={**_range("2026-10-28", "2026-10-29"), "synthetic": "true"},
    ).json()

    # Two active days, then four observed/unknown days: every bucket is present.
    assert len(body["buckets"]) == 2
    assert body["totals"]["detections"] == loaded_fixture["inserted"]

    bucket = body["buckets"][0]
    assert bucket["start"] == "2026-10-28"
    assert bucket["detections"] == 5
    assert bucket["modis"] + bucket["viirs"] == bucket["detections"]
    assert bucket["frp_sum_mw"] >= (bucket["frp_max_mw"] or 0)
    assert bucket["frp_max_mw"] > 0
    assert 0 <= bucket["high_confidence"] <= bucket["detections"]
    assert bucket["state"] == "active"


def test_calendar_separates_quiet_from_unobserved(
    client: TestClient, loaded_fixture: dict
) -> None:
    # One day observed and empty, one day with no availability record at all.
    _record_availability("MODIS_SP", [("2026-10-30", "empty")])
    _record_availability("VIIRS_SNPP_SP", [("2026-10-30", "empty")])

    body = client.get(
        "/api/v1/calendar", params={**_range(), "synthetic": "true"}
    ).json()
    by_day = {bucket["start"]: bucket for bucket in body["buckets"]}

    quiet = by_day["2026-10-30"]
    assert quiet["detections"] == 0
    assert quiet["state"] == "quiet"
    assert quiet["coverage"]["empty"] == 1
    assert quiet["coverage"]["observed"] == 1

    unobserved = by_day["2026-10-26"]
    assert unobserved["detections"] == 0
    assert unobserved["state"] == "unobserved"
    assert unobserved["coverage"]["unknown"] == 1

    notes = " ".join(body["notes"]).lower()
    assert "not fires" in notes
    assert "unobserved" in notes


def test_calendar_marks_missing_availability(client: TestClient, loaded_fixture: dict) -> None:
    _record_availability("MODIS_SP", [("2026-10-31", "not_yet_available")])

    body = client.get("/api/v1/calendar", params={**_range(), "synthetic": "true"}).json()
    bucket = {item["start"]: item for item in body["buckets"]}["2026-10-31"]

    assert bucket["coverage"]["missing"] == 1
    assert bucket["state"] == "unobserved"


def test_calendar_granularity_buckets_roll_up(
    client: TestClient, loaded_fixture: dict
) -> None:
    day = client.get(
        "/api/v1/calendar", params={**_range(), "synthetic": "true"}
    ).json()
    month = client.get(
        "/api/v1/calendar",
        params={**_range(), "granularity": "month", "synthetic": "true"},
    ).json()

    assert len(month["buckets"]) == 1
    assert month["buckets"][0]["start"] == "2026-10-01"
    assert month["buckets"][0]["end"] == "2026-10-31"
    assert month["buckets"][0]["detections"] == day["totals"]["detections"]


def test_calendar_rejects_bad_requests(client: TestClient) -> None:
    inverted = client.get(
        "/api/v1/calendar", params={"start_date": "2026-10-31", "end_date": "2026-10-01"}
    )
    assert inverted.status_code == 400
    assert inverted.json()["error"]["code"] == "bad_request"

    bad_granularity = client.get("/api/v1/calendar", params={**_range(), "granularity": "hour"})
    assert bad_granularity.status_code == 400

    too_long = client.get(
        "/api/v1/calendar", params={"start_date": "2015-01-01", "end_date": "2026-10-01"}
    )
    assert too_long.status_code == 400


def test_calendar_requires_dates(client: TestClient) -> None:
    assert client.get("/api/v1/calendar").status_code == 422


def test_drilldown_returns_the_source_observations(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/calendar/drilldown",
        params={
            "bucket_start": "2026-10-28",
            "granularity": "day",
            "synthetic": "true",
            "limit": 500,
        },
    ).json()

    assert body["bucket"]["start"] == "2026-10-28"
    assert body["bucket"]["state"] == "active"
    assert body["bucket"]["detections"] == 5
    assert body["total"] == body["bucket"]["detections"]
    assert len(body["items"]) == body["total"]
    assert {item["sensor"] for item in body["items"]} == {"MODIS", "VIIRS"}
    assert all(item["source_record_id"] for item in body["items"])


def test_drilldown_respects_filters_and_bounds(client: TestClient, loaded_fixture: dict) -> None:
    body = client.get(
        "/api/v1/calendar/drilldown",
        params={
            "bucket_start": "2026-10-28",
            "granularity": "month",
            "sensor": "MODIS",
            "limit": 2,
            "synthetic": "true",
        },
    ).json()

    assert body["bucket"]["start"] == "2026-10-01"
    assert body["bucket"]["viirs"] == 0
    assert body["returned"] == 2
    assert body["total"] > body["returned"]
    assert all(item["sensor"] == "MODIS" for item in body["items"])


def test_time_window_narrows_observations_and_aggregates(
    client: TestClient, loaded_fixture: dict
) -> None:
    window = {"start_at": "2026-10-28T10:30:00Z", "end_at": "2026-10-28T11:00:00Z"}

    everything = client.get("/api/v1/fires", params={"synthetic": "true"}).json()
    windowed = client.get(
        "/api/v1/fires", params={**window, "synthetic": "true"}
    ).json()

    assert 0 < windowed["total"] < everything["total"]
    for row in windowed["items"]:
        assert "10:30" <= row["acquired_at"][11:16] < "11:00"

    calendar = client.get(
        "/api/v1/calendar",
        params={
            "start_date": "2026-10-28",
            "end_date": "2026-10-28",
            "synthetic": "true",
            **window,
        },
    ).json()
    assert calendar["totals"]["detections"] == windowed["total"]


def test_time_window_must_be_ordered(client: TestClient) -> None:
    response = client.get(
        "/api/v1/fires",
        params={"start_at": "2026-10-28T12:00:00Z", "end_at": "2026-10-28T11:00:00Z"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_bucket_helpers_cover_the_range() -> None:
    start, end = date(2026, 1, 30), date(2026, 2, 2)
    week_buckets = buckets_between(start, end, "week")
    assert week_buckets[0].start == date(2026, 1, 26)
    assert all(
        later.start > earlier.start
        for earlier, later in zip(week_buckets, week_buckets[1:], strict=False)
    )

    assert bucket_for(date(2026, 2, 17), "month").end == date(2026, 2, 28)
    assert bucket_for(date(2026, 12, 5), "year") == (
        bucket_for(date(2026, 12, 5), "year")
    )
    assert bucket_for(date(2026, 12, 5), "year").start == date(2026, 1, 1)

    try:
        validate_span(date(2026, 1, 1), date(2026, 1, 1) + timedelta(days=4000))
    except Exception as error:  # noqa: BLE001 - asserted below
        assert getattr(error, "code", "") == "bad_request"
    else:  # pragma: no cover - the call must raise
        raise AssertionError("expected the span guard to reject a 4000-day range")
