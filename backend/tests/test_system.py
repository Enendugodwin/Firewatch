"""System status, module registry and data-source catalogue."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_status_reports_no_data_instead_of_fake_activity(client: TestClient) -> None:
    body = client.get("/api/v1/system/status").json()

    assert body["data"]["freshness"] == "no_data"
    assert body["data"]["firms_configured"] is False
    assert body["data"]["observations_stored"] == 0
    assert body["data"]["last_observation_at"] is None
    assert "FIRMS_MAP_KEY is not configured" in body["data"]["freshness_reason"]


def test_status_exposes_phase_and_capabilities(client: TestClient) -> None:
    body = client.get("/api/v1/system/status").json()

    assert body["phase"] == "3"
    assert body["phase_name"] == "Harmonization"
    assert body["capabilities"]["authentication"] is False
    # Ingestion is implemented; it reports unavailable until a MAP_KEY exists.
    assert body["capabilities"]["ingestion"] is False
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


def test_only_delivered_modules_claim_readiness(client: TestClient) -> None:
    modules = {module["key"]: module for module in client.get("/api/v1/system/modules").json()}

    # Phase 3 delivered the harmonization workspace; nothing beyond it may claim
    # readiness until its own phase lands.
    assert modules["harmonization"]["status"] == "ready"
    for key in (
        "fire-map",
        "calendar",
        "analytics",
        "anomalies",
        "regions",
        "exposure",
        "reports",
        "assistant",
    ):
        assert modules[key]["status"] == "scaffolded", key


def test_sources_are_registered_but_empty(client: TestClient) -> None:
    sources = client.get("/api/v1/system/sources").json()

    assert len(sources) == 8
    codes = {source["code"] for source in sources}
    assert {"MODIS_SP", "VIIRS_SNPP_SP", "VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP"} <= codes
    assert {"MODIS_NRT", "VIIRS_NOAA21_NRT"} <= codes
    assert all(source["status"] == "not_ingested" for source in sources)
    assert all(source["observations"] == 0 for source in sources)
