"""Regional engine: boundaries, exact counts, trend statistics and honest gates."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.errors import AppError
from app.db.models import FireObservation
from app.db.session import session_scope
from app.services.geometry import (
    circle_boundary,
    load_boundary,
    mask_points,
    parse_boundary,
)
from app.services.regional import _current_month, mann_kendall

# The synthetic fixture sits around 8.5 N, 9.1 E.
# The synthetic fixture spans 6.1-9.9 N and 7.2-10.9 E.
FIXTURE_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [6.50, 5.50],
            [11.50, 5.50],
            [11.50, 10.50],
            [6.50, 10.50],
            [6.50, 5.50],
        ]
    ],
}

HALF_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [9.00, 8.40],
            [11.50, 8.40],
            [11.50, 8.60],
            [9.00, 8.60],
            [9.00, 8.40],
        ]
    ],
}

WINDOW = {"start_date": "2026-10-26", "end_date": "2026-10-31"}

WINDOW_DAYS = [date(2026, 10, day) for day in range(26, 32)]


def _record_full_coverage() -> None:
    """Mark every day in the window as observed so coverage gates can pass."""
    from app.db.models import DataSource, SourceAvailability

    with session_scope() as session:
        for code in ("MODIS_SP", "VIIRS_SNPP_SP"):
            source = session.scalar(select(DataSource).where(DataSource.source_code == code))
            assert source is not None
            for day in WINDOW_DAYS:
                existing = session.scalar(
                    select(SourceAvailability).where(
                        SourceAvailability.source_id == source.id,
                        SourceAvailability.observation_date == day,
                    )
                )
                if existing is None:
                    session.add(
                        SourceAvailability(
                            source_id=source.id, observation_date=day, status="available"
                        )
                    )
                else:
                    existing.status = "available"


def test_parse_polygon_and_reject_unsupported_shapes() -> None:
    boundary = parse_boundary(FIXTURE_POLYGON)

    assert boundary.geometry["type"] == "MultiPolygon"
    assert boundary.bbox == (6.5, 5.5, 11.5, 10.5)
    assert boundary.vertices == 5
    assert boundary.area_km2 > 0

    with pytest.raises(AppError) as point_error:
        parse_boundary({"type": "Point", "coordinates": [9.1, 8.5]})
    assert point_error.value.code == "bad_request"

    crossing = {
        "type": "Polygon",
        "coordinates": [
            [[-179.0, 0.0], [179.0, 0.0], [179.0, 1.0], [-179.0, 1.0], [-179.0, 0.0]]
        ],
    }
    with pytest.raises(AppError):
        parse_boundary(crossing)


def test_polygon_holes_are_respected() -> None:
    with_hole = {
        "type": "Polygon",
        "coordinates": [
            [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]],
            [[4.0, 4.0], [6.0, 4.0], [6.0, 6.0], [4.0, 6.0], [4.0, 4.0]],
        ],
    }
    boundary = parse_boundary(with_hole)
    shape = boundary.to_shape()

    inside = mask_points(shape, np.array([2.0, 5.0]), np.array([2.0, 5.0]))
    assert inside.tolist() == [True, False]


def test_circle_boundary_has_the_requested_scale() -> None:
    boundary = circle_boundary(0.0, 0.0, 100.0)
    # πr² = 31 416 km²; the flat approximation should be within a few percent.
    assert 29_000 <= boundary.area_km2 <= 33_500
    assert boundary.bbox[0] < 0 < boundary.bbox[2]


def test_catalog_seeds_approximate_country_regions(client: TestClient) -> None:
    first = client.get("/api/v1/regions/catalog", params={"level": "country", "q": "Nigeria"})
    assert first.status_code == 200
    body = first.json()
    nigeria = next(region for region in body["regions"] if region["name"] == "Nigeria")
    assert nigeria["is_approximate"] is True
    assert nigeria["boundary_kind"] == "bbox"
    assert len(nigeria["bbox"]) == 4

    # Seeding is idempotent.
    second = client.get("/api/v1/regions/catalog", params={"level": "country", "q": "Nigeria"})
    assert second.json()["total"] == body["total"]


def test_custom_region_roundtrip(client: TestClient) -> None:
    created = client.post(
        "/api/v1/regions/custom",
        json={"name": "Fixture box", "geometry": FIXTURE_POLYGON, "level": "custom"},
    )
    assert created.status_code == 201
    region = created.json()
    assert region["boundary_kind"] == "polygon"
    assert region["is_approximate"] is False
    assert region["geometry"] is None  # geometry is opt-in

    detail = client.get(
        f"/api/v1/regions/{region['id']}", params={"include_geometry": "true"}
    )
    assert detail.status_code == 200
    assert detail.json()["geometry"]["type"] == "MultiPolygon"


def test_custom_region_rejects_bad_geometry(client: TestClient) -> None:
    response = client.post(
        "/api/v1/regions/custom",
        json={"name": "Not a polygon", "geometry": {"type": "Point", "coordinates": [1, 2]}},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_analyze_counts_only_points_inside_the_polygon(
    client: TestClient, loaded_fixture: dict
) -> None:
    region = client.post(
        "/api/v1/regions/custom",
        json={"name": "Half fixture box", "geometry": HALF_POLYGON},
    ).json()

    analyzed = client.post(
        f"/api/v1/regions/{region['id']}/analyze",
        json={**WINDOW, "synthetic": True},
    ).json()
    assert analyzed["status"] == "ok"

    # Expected count: exact point-in-polygon over the stored fixture rows.
    shape = load_boundary(parse_boundary(HALF_POLYGON).geometry).to_shape()
    with session_scope() as session:
        rows = session.execute(
            select(FireObservation.longitude, FireObservation.latitude).where(
                FireObservation.is_synthetic.is_(True)
            )
        ).all()
    lons = np.array([row.longitude for row in rows])
    lats = np.array([row.latitude for row in rows])
    expected = int(mask_points(shape, lons, lats).sum())

    assert analyzed["detections_in_region"] == expected
    assert 0 < expected < loaded_fixture["inserted"]

    overview = client.get(
        f"/api/v1/regions/{region['id']}/overview", params=WINDOW
    ).json()
    assert overview["status"] == "ok"
    assert overview["totals"]["detections"] == expected
    assert 0 < overview["totals"]["coverage"] <= 1


def test_full_analysis_reads_from_materialised_statistics(
    client: TestClient, loaded_fixture: dict
) -> None:
    _record_full_coverage()
    region = client.post(
        "/api/v1/regions/custom",
        json={"name": "Whole fixture box", "geometry": FIXTURE_POLYGON},
    ).json()
    analyzed = client.post(
        f"/api/v1/regions/{region['id']}/analyze",
        json={**WINDOW, "synthetic": True},
    ).json()
    assert analyzed["detections_in_region"] == loaded_fixture["inserted"]

    base = f"/api/v1/regions/{region['id']}"
    overview = client.get(f"{base}/overview", params=WINDOW).json()
    assert overview["totals"]["detections"] == loaded_fixture["inserted"]
    assert 0 < overview["totals"]["coverage"] <= 1

    monthly = client.get(f"{base}/monthly", params=WINDOW).json()
    assert monthly["status"] == "ok"
    assert sum(month["detections"] for month in monthly["months"]) == loaded_fixture["inserted"]

    yearly = client.get(f"{base}/yearly", params=WINDOW).json()
    assert [year["year"] for year in yearly["years"]] == [2026]

    seasonality = client.get(f"{base}/seasonality", params=WINDOW).json()
    assert seasonality["status"] == "single_year"
    assert seasonality["peak_month"] is None
    assert len(seasonality["day_of_year"]["points"]) == 366

    trends = client.get(f"{base}/trends", params=WINDOW).json()
    assert trends["status"] == "insufficient_years"
    assert trends["mann_kendall"]["trend"] in {"unknown", "no_significant_trend"}

    anomalies = client.get(f"{base}/anomalies", params=WINDOW).json()
    assert anomalies["status"] == "insufficient_history"
    assert anomalies["count"] == 0

    spatial = client.get(f"{base}/spatial-activity").json()
    assert spatial["status"] == "ok"
    assert spatial["grid_degrees"] == 0.5
    assert sum(cell["detections"] for cell in spatial["cells"]) == loaded_fixture["inserted"]

    sensors = client.get(f"{base}/sensor-comparison", params=WINDOW).json()
    assert sensors["status"] == "ok"
    assert set(sensors["sensors"]) == {"MODIS", "VIIRS"}

    exported = client.get(f"{base}/export", params=WINDOW)
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    assert "period_type" in exported.text


def test_unanalyzed_region_reports_not_analyzed(client: TestClient) -> None:
    region = client.post(
        "/api/v1/regions/custom",
        json={"name": "Never analysed", "geometry": FIXTURE_POLYGON},
    ).json()

    overview = client.get(
        f"/api/v1/regions/{region['id']}/overview", params=WINDOW
    ).json()
    assert overview["status"] == "not_analyzed"
    assert "analyze" in overview["requirements"]["note"]

    export = client.get(f"/api/v1/regions/{region['id']}/export", params=WINDOW)
    assert export.status_code == 404


def test_radius_region_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/v1/regions/radius",
        json={
            "name": "Fixture radius",
            "latitude": 8.5,
            "longitude": 9.1,
            "radius_km": 25,
        },
    )
    assert response.status_code == 201
    region = response.json()
    assert region["boundary_kind"] == "circle"
    assert region["level"] == "radius"


def test_mann_kendall_detects_a_monotonic_trend() -> None:
    increasing = mann_kendall([10, 14, 19, 24, 30, 38, 45, 51, 60, 68])
    assert increasing["status"] == "ok"
    assert increasing["trend"] == "significant_increase"
    assert increasing["p_value"] < 0.05
    assert increasing["sen_slope_per_year"] > 0

    flat = mann_kendall([20, 21, 19, 20, 20.5, 19.5, 20, 20.2, 19.8, 20.1])
    assert flat["trend"] == "no_significant_trend"

    assert mann_kendall([1, 2])["status"] == "insufficient_data"


def test_sensor_comparison_flags_a_single_sensor_window(
    client: TestClient, loaded_fixture: dict
) -> None:
    region = client.post(
        "/api/v1/regions/custom",
        json={"name": "MODIS-only box", "geometry": FIXTURE_POLYGON},
    ).json()
    client.post(
        f"/api/v1/regions/{region['id']}/analyze",
        json={**WINDOW, "synthetic": True, "sensor": "MODIS"},
    )
    comparison = client.get(
        f"/api/v1/regions/{region['id']}/sensor-comparison", params=WINDOW
    ).json()
    assert comparison["status"] == "single_sensor"
    assert set(comparison["sensors"]) == {"MODIS"}
    assert comparison["correlation"] is None


def _month(year: int, month: int, detections: int, coverage: float = 1.0) -> dict:
    return {"year": year, "month": month, "detections": detections, "coverage": coverage}


def test_current_month_compares_with_prior_years_of_the_same_month() -> None:
    months = [
        _month(2022, 10, 100),
        _month(2023, 10, 200),
        _month(2024, 10, 300),
        _month(2026, 10, 600),
        _month(2026, 9, 9999),
    ]
    block = _current_month(months, end=date(2026, 10, 31))

    assert block["status"] == "ok"
    assert block["observed"] == 600
    assert block["median"] == 200
    assert block["baseline_years"] == 3
    assert block["deviation_ratio"] == 2.0


def test_current_month_withholds_the_comparison_without_history() -> None:
    block = _current_month([_month(2026, 10, 600)], end=date(2026, 10, 31))
    assert block["status"] == "insufficient_history"
    assert block["observed"] == 600
    assert block["median"] is None

    missing = _current_month([_month(2025, 10, 100)], end=date(2026, 10, 31))
    assert missing["status"] == "no_current_data"
