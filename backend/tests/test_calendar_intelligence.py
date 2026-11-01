"""Fire-calendar intelligence: trend, anomaly markers and seasonal gating.

The seasonal gate is the important one: with a single year of history the engine
must show a profile but refuse to call it a climatology.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

from fastapi.testclient import TestClient

from app.services.trends import (
    _seasonality_block,
    theil_sen,
    trailing_mean,
)


def _daily_year(year: int, *, base: float, july: float) -> tuple[dict, set[date]]:
    """Every day of one year observed, with a deliberate July peak."""
    daily: dict[date, dict[str, float]] = {}
    observed: set[date] = set()
    for month in range(1, 13):
        for day_number in range(1, monthrange(year, month)[1] + 1):
            day = date(year, month, day_number)
            daily[day] = {"detections": july if month == 7 else base}
            observed.add(day)
    return daily, observed


def test_theil_sen_recovers_a_line_and_resists_one_outlier() -> None:
    xs = [float(index) for index in range(30)]
    ys = [2.0 * x + 5.0 for x in xs]
    slope, intercept = theil_sen(xs, ys)
    assert round(slope, 6) == 2.0
    assert round(intercept, 6) == 5.0

    outlier = list(ys)
    outlier[10] = 10_000.0
    robust_slope, _ = theil_sen(xs, outlier)
    # A least-squares fit would be dragged upward; the median slope is not.
    assert robust_slope == 2.0


def test_trailing_mean_skips_gaps_instead_of_zero_filling() -> None:
    smoothed = trailing_mean([10.0, None, 12.0, 14.0], window=2)
    assert smoothed == [10.0, None, 11.0, 13.0]


def test_seasonality_refuses_a_single_year_profile() -> None:
    daily, observed = _daily_year(2026, base=10.0, july=100.0)

    block = _seasonality_block(
        daily, observed, first_year=2026, last_year=2026, metric="detections"
    )

    assert block["status"] == "single_year"
    assert block["years"] == [2026]
    assert block["peak_month"] is None
    assert block["trough_month"] is None
    assert block["seasonal_amplitude"] is None
    assert all(month["index"] is None for month in block["months"])
    assert "not a seasonal climatology" in block["requirements"]["note"]


def test_seasonality_profile_needs_two_years_of_coverage() -> None:
    daily: dict = {}
    observed: set[date] = set()
    for year in (2025, 2026):
        year_daily, year_observed = _daily_year(year, base=10.0, july=100.0)
        daily.update(year_daily)
        observed |= year_observed

    block = _seasonality_block(
        daily, observed, first_year=2025, last_year=2026, metric="detections"
    )

    assert block["status"] == "ok"
    assert block["years"] == [2025, 2026]
    assert block["sufficient_months"] == 12
    assert block["peak_month"] == "Jul"
    assert block["trough_month"] == "Jan"
    assert 9.9 <= block["seasonal_amplitude"] <= 10.1

    by_label = {month["label"]: month for month in block["months"]}
    assert by_label["Jul"]["years"] == 2
    assert by_label["Jul"]["index"] > 5
    assert by_label["Jan"]["index"] < 1


def test_seasonality_is_partial_when_months_lack_coverage() -> None:
    daily: dict = {}
    observed: set[date] = set()
    for year in (2025, 2026):
        for month in range(1, 6):  # only five months in each year
            for day_number in range(1, monthrange(year, month)[1] + 1):
                day = date(year, month, day_number)
                daily[day] = {"detections": 20.0}
                observed.add(day)

    block = _seasonality_block(
        daily, observed, first_year=2025, last_year=2026, metric="detections"
    )

    assert block["status"] == "partial"
    assert block["sufficient_months"] == 5
    assert block["peak_month"] is None
    assert block["trough_month"] is None


def test_api_reports_trend_series_and_withholds_seasonality(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/calendar/intelligence",
        params={
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
            "synthetic": "true",
        },
    ).json()

    assert body["status"] == "ok"
    assert body["window"]["days"] == 31
    assert body["window"]["observed_days"] >= 2
    assert body["window"]["missing_days"] == 31 - body["window"]["observed_days"]

    series = body["trend"]["series"]
    assert len(series) == 31
    assert series[0]["date"] == "2026-10-01"

    by_day = {point["date"]: point for point in series}
    active = by_day["2026-10-28"]
    assert active["observed"] is True
    assert active["value"] is not None

    # A day with no availability record is a gap, not a zero.
    gap = by_day["2026-10-05"]
    assert gap["observed"] is False
    assert gap["value"] is None
    assert gap["severity"] == "unobserved"

    # Two observed days cannot support a trend or a climatology.
    assert body["trend"]["status"] == "insufficient_history"
    assert body["trend"]["slope_per_30_days"] is None
    assert body["seasonality"]["status"] == "single_year"
    assert body["seasonality"]["peak_month"] is None

    notes = " ".join(body["notes"]).lower()
    assert "not fires" in notes
    assert "never zero" in notes or "excluded" in notes


def test_api_honours_metric_and_rejects_inverted_ranges(
    client: TestClient, loaded_fixture: dict
) -> None:
    frp = client.get(
        "/api/v1/calendar/intelligence",
        params={
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
            "metric": "frp",
            "synthetic": "true",
        },
    ).json()
    assert frp["window"]["metric"] == "frp"
    assert frp["trend"]["metric"] == "frp"

    inverted = client.get(
        "/api/v1/calendar/intelligence",
        params={"start_date": "2026-10-31", "end_date": "2026-10-01"},
    )
    assert inverted.status_code == 400
    assert inverted.json()["error"]["code"] == "bad_request"


def test_api_marks_trailing_mean_over_observed_days_only(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/calendar/intelligence",
        params={
            "start_date": "2026-10-26",
            "end_date": "2026-10-31",
            "synthetic": "true",
        },
    ).json()

    for point in body["trend"]["series"]:
        if point["value"] is None:
            assert point["trailing_mean"] is None
        else:
            assert point["trailing_mean"] is not None
