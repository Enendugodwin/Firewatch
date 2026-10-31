"""Analytics summaries: reconciliation, series shape, rankings and filters."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_summary_reconciles_with_stored_observations(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/analytics/summary",
        params={
            "start_date": "2026-10-26",
            "end_date": "2026-10-31",
            "synthetic": "true",
        },
    ).json()

    assert body["totals"]["detections"] == loaded_fixture["inserted"]
    assert body["totals"]["modis"] + body["totals"]["viirs"] == body["totals"]["detections"]
    assert len(body["series"]) == 6
    assert sum(point["detections"] for point in body["series"]) == loaded_fixture["inserted"]
    assert body["totals"]["active_days"] == 2
    assert body["totals"]["days"] == 6


def test_series_covers_every_day_even_without_detections(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/analytics/summary",
        params={"start_date": "2026-10-26", "end_date": "2026-10-31", "synthetic": "true"},
    ).json()

    dates = [point["date"] for point in body["series"]]
    assert dates == [
        "2026-10-26",
        "2026-10-27",
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
        "2026-10-31",
    ]
    assert body["series"][0]["detections"] == 0
    assert body["series"][2]["detections"] > 0


def test_rankings_are_cells_not_countries(client: TestClient, loaded_fixture: dict) -> None:
    body = client.get(
        "/api/v1/analytics/summary",
        params={
            "start_date": "2026-10-26",
            "end_date": "2026-10-31",
            "synthetic": "true",
            "top": 5,
        },
    ).json()

    cells = body["top_cells"]
    assert 0 < len(cells) <= 5
    assert body["cell_degrees"] > 0
    counts = [cell["detections"] for cell in cells]
    assert counts == sorted(counts, reverse=True)
    # The fixture sits over northern Nigeria; a coarse grid cell contains it.
    assert any(4 < cell["latitude"] < 14 and 2 < cell["longitude"] < 15 for cell in cells)
    assert "not administrative boundaries" in " ".join(body["notes"])


def test_sensor_filter_narrows_the_breakdown(client: TestClient, loaded_fixture: dict) -> None:
    body = client.get(
        "/api/v1/analytics/summary",
        params={
            "start_date": "2026-10-26",
            "end_date": "2026-10-31",
            "synthetic": "true",
            "sensor": "MODIS",
        },
    ).json()

    assert body["totals"]["viirs"] == 0
    assert body["totals"]["modis"] == body["totals"]["detections"]
    assert body["daynight"]["N"] == 0


def test_confidence_and_sensor_breakdowns_reconcile(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/analytics/summary",
        params={"start_date": "2026-10-26", "end_date": "2026-10-31", "synthetic": "true"},
    ).json()

    assert sum(body["confidence"].values()) == body["totals"]["detections"]
    assert sum(body["daynight"].values()) == body["totals"]["detections"]
    assert sum(item["detections"] for item in body["satellites"]) == body["totals"]["detections"]
    assert sum(item["detections"] for item in body["products"]) == body["totals"]["detections"]


def test_summary_rejects_inverted_ranges(client: TestClient) -> None:
    response = client.get(
        "/api/v1/analytics/summary",
        params={"start_date": "2026-10-31", "end_date": "2026-10-01"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_summary_requires_dates(client: TestClient) -> None:
    assert client.get("/api/v1/analytics/summary").status_code == 422
