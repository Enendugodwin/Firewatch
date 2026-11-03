"""The calendar exposes a harmonised series alongside the raw sensor counts."""

from __future__ import annotations

from fastapi.testclient import TestClient

WINDOW = {
    "start_date": "2026-10-26",
    "end_date": "2026-10-30",
    "granularity": "day",
    "synthetic": "true",
}


def test_calendar_buckets_carry_harmonized_counts(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get("/api/v1/calendar", params=WINDOW).json()

    buckets = body["buckets"]
    assert buckets

    matched_total = 0
    for bucket in buckets:
        assert bucket["harmonized"] == bucket["detections"] - bucket["matched_viirs"]
        assert 0 <= bucket["matched_viirs"] <= bucket["viirs"]
        matched_total += bucket["matched_viirs"]

    assert matched_total > 0, "the fixture has cross-sensor associations"
    assert body["totals"]["matched_viirs"] == matched_total
    assert body["totals"]["harmonized"] == body["totals"]["detections"] - matched_total
    assert any("harmonized" in note for note in body["notes"])


def test_a_modis_only_calendar_has_nothing_to_deduplicate(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/calendar", params={**WINDOW, "sensor": "MODIS"}
    ).json()

    assert body["buckets"]
    assert all(bucket["matched_viirs"] == 0 for bucket in body["buckets"])
    assert all(
        bucket["harmonized"] == bucket["detections"] for bucket in body["buckets"]
    )
