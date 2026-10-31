"""Map endpoints: viewport aggregation and geographic search."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.map_aggregation import grid_degrees


def test_aggregate_reconciles_with_stored_observations(
    client: TestClient, loaded_fixture: dict
) -> None:
    response = client.get(
        "/api/v1/fires/aggregate",
        params={"bbox": "2,4,15,14", "zoom": 6},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["cells"], "expected aggregated cells"
    assert body["total_detections"] == loaded_fixture["inserted"]
    assert body["returned_cells"] == len(body["cells"])
    assert body["truncated"] is False
    assert body["cell_degrees"] == grid_degrees(6)

    total = sum(cell["count"] for cell in body["cells"])
    modis = sum(cell["modis"] for cell in body["cells"])
    viirs = sum(cell["viirs"] for cell in body["cells"])

    assert total == body["total_detections"]
    assert modis == 5
    assert viirs == 4
    assert max(cell["max_frp_mw"] for cell in body["cells"]) > 0


def test_aggregate_cells_shrink_with_zoom(client: TestClient, loaded_fixture: dict) -> None:
    coarse = client.get("/api/v1/fires/aggregate", params={"bbox": "2,4,15,14", "zoom": 2}).json()
    fine = client.get("/api/v1/fires/aggregate", params={"bbox": "2,4,15,14", "zoom": 9}).json()

    assert fine["cell_degrees"] < coarse["cell_degrees"]
    assert fine["returned_cells"] >= coarse["returned_cells"]
    assert fine["total_detections"] == coarse["total_detections"]


def test_aggregate_respects_filters(client: TestClient, loaded_fixture: dict) -> None:
    body = client.get(
        "/api/v1/fires/aggregate",
        params={"bbox": "2,4,15,14", "zoom": 6, "sensor": "MODIS"},
    ).json()

    assert body["total_detections"] == 5
    assert all(cell["viirs"] == 0 for cell in body["cells"])


def test_aggregate_requires_and_validates_bbox(client: TestClient) -> None:
    assert client.get("/api/v1/fires/aggregate").status_code == 422

    inverted = client.get("/api/v1/fires/aggregate", params={"bbox": "10,4,5,14"})
    assert inverted.status_code == 400
    assert inverted.json()["error"]["code"] == "bad_request"


def test_aggregate_rejects_impossible_zoom(client: TestClient) -> None:
    response = client.get("/api/v1/fires/aggregate", params={"bbox": "2,4,15,14", "zoom": 30})
    assert response.status_code == 422


def test_grid_degrees_is_clamped() -> None:
    assert grid_degrees(0) == 45.0
    assert grid_degrees(20) == 0.05
    assert grid_degrees(6) < grid_degrees(3)


def test_geo_search_prioritises_countries(client: TestClient) -> None:
    body = client.get("/api/v1/geo/search", params={"q": "nig"}).json()

    names = [result["name"] for result in body["results"]]
    assert "Nigeria" in names
    assert "Niger" in names
    assert all(result["kind"] == "country" for result in body["results"])
    assert -90 <= body["results"][0]["latitude"] <= 90


def test_geo_search_accepts_coordinates(client: TestClient) -> None:
    body = client.get("/api/v1/geo/search", params={"q": "8.5, 9.1"}).json()

    assert body["results"][0]["kind"] == "coordinates"
    assert body["results"][0]["latitude"] == 8.5
    assert body["results"][0]["longitude"] == 9.1


def test_geo_search_finds_cities(client: TestClient) -> None:
    body = client.get("/api/v1/geo/search", params={"q": "lagos"}).json()

    assert body["results"][0]["name"] == "Lagos"
    assert body["results"][0]["kind"] == "city"


def test_geo_search_returns_empty_for_nonsense(client: TestClient) -> None:
    body = client.get("/api/v1/geo/search", params={"q": "zzzzqqq"}).json()

    assert body["count"] == 0
    assert body["results"] == []


def test_geo_search_rejects_out_of_range_coordinates(client: TestClient) -> None:
    body = client.get("/api/v1/geo/search", params={"q": "120, 200"}).json()

    assert body["results"] == []

def test_min_confidence_filter_is_applied(client: TestClient, loaded_fixture: dict) -> None:
    high = client.get("/api/v1/fires", params={"min_confidence": "high"}).json()
    nominal = client.get("/api/v1/fires", params={"min_confidence": "nominal"}).json()

    assert high["total"] == 5
    assert all(item["confidence_category"] == "high" for item in high["items"])
    assert nominal["total"] == 7
    assert all(
        item["confidence_category"] in {"nominal", "high"} for item in nominal["items"]
    )

    aggregated = client.get(
        "/api/v1/fires/aggregate",
        params={"bbox": "2,4,15,14", "zoom": 6, "min_confidence": "high"},
    ).json()
    assert aggregated["total_detections"] == 5


def test_unknown_confidence_value_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/fires", params={"min_confidence": "certain"})
    assert response.status_code == 422
