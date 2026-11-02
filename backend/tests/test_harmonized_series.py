"""Harmonised series: raw counts minus cross-sensor duplicates, honestly gated."""

from __future__ import annotations

from fastapi.testclient import TestClient

WINDOW = {"start_date": "2026-10-26", "end_date": "2026-10-31", "synthetic": "true"}


def test_series_reconciles_and_subtracts_matched_viirs(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get("/api/v1/harmonization/series", params=WINDOW).json()

    assert body["status"] == "ok"
    assert body["algorithm_version"] == "harmonized-series-v1"
    assert "MODIS + VIIRS" in body["definition"]

    totals = body["totals"]
    assert totals["raw"] == totals["modis"] + totals["viirs"]
    assert totals["harmonized"] == totals["raw"] - totals["matched_viirs"]
    assert totals["raw"] == loaded_fixture["inserted"]
    assert totals["matched_viirs"] > 0
    assert totals["harmonized"] < totals["raw"]

    days = body["days"]
    assert [day["date"] for day in days] == sorted(day["date"] for day in days)
    assert all(day["harmonized"] <= day["raw"] for day in days)
    assert body["coverage"]["days_with_matches"] > 0

    notes = " ".join(body["notes"]).lower()
    assert "not a calibrated fire count" in notes
    assert "not fires" in notes


def test_series_without_associations_says_so(client: TestClient) -> None:
    body = client.get(
        "/api/v1/harmonization/series",
        params={"start_date": "2020-01-01", "end_date": "2020-01-02"},
    ).json()

    assert body["status"] == "unmatched"
    assert body["totals"]["matched_viirs"] == 0
    assert body["totals"]["harmonized"] == body["totals"]["raw"]
    assert "not evidence that no duplicates exist" in " ".join(body["notes"])


def test_series_rejects_unknown_statuses(client: TestClient) -> None:
    response = client.get(
        "/api/v1/harmonization/series",
        params={**WINDOW, "statuses": "rejected"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"
