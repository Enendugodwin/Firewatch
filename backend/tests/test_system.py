"""System status, module registry and data-source catalogue."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_status_reports_no_data_instead_of_fake_activity(client: TestClient) -> None:
    body = client.get("/api/v1/system/status").json()

    assert body["data"]["freshness"] == "no_data"
    assert body["data"]["firms_configured"] is False
    assert body["data"]["observations_stored"] is None
    assert body["data"]["last_observation_at"] is None
    assert "FIRMS_MAP_KEY is not configured" in body["data"]["freshness_reason"]


def test_status_exposes_phase_and_capabilities(client: TestClient) -> None:
    body = client.get("/api/v1/system/status").json()

    assert body["phase"] == "1"
    assert body["phase_name"] == "Foundation"
    assert body["capabilities"]["ingestion"] is False
    assert body["capabilities"]["authentication"] is False
    # SQLite has no spatial extension, so spatial capability is honestly false.
    assert body["capabilities"]["spatial"] is False


def test_module_registry_covers_every_product_module(client: TestClient) -> None:
    modules = client.get("/api/v1/system/modules").json()

    keys = [module["key"] for module in modules]
    assert keys == [
        "overview",
        "fire-map",
        "calendar",
        "analytics",
        "harmonization",
        "anomalies",
        "regions",
        "exposure",
        "reports",
        "assistant",
        "settings",
    ]
    for module in modules:
        assert module["route"].startswith("/")
        assert module["status"] in {"scaffolded", "in_progress", "ready"}
        assert module["planned"], f"{module['key']} must list planned capabilities"


def test_only_settings_is_in_progress_in_phase_one(client: TestClient) -> None:
    modules = client.get("/api/v1/system/modules").json()

    in_progress = {m["key"] for m in modules if m["status"] == "in_progress"}
    assert in_progress == {"settings"}
    # No analytical module may claim to be ready before it is built.
    assert all(m["status"] != "ready" for m in modules)


def test_sources_are_not_ingested_yet(client: TestClient) -> None:
    sources = client.get("/api/v1/system/sources").json()

    assert len(sources) == 8
    codes = {source["code"] for source in sources}
    assert {"MODIS_SP", "VIIRS_SNPP_SP", "VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP"} <= codes
    assert {"MODIS_NRT", "VIIRS_NOAA21_NRT"} <= codes
    assert all(source["status"] == "not_ingested" for source in sources)
