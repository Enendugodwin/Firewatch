"""Module registry.

Single source of truth for the ten product modules plus settings, used by the
API (``/api/v1/system/modules``) and surfaced in the UI so that a module is
never presented as complete before it is. ``status`` is intentionally coarse:

* ``scaffolded`` — route + shell exist, no analytical capability yet.
* ``in_progress`` — partially implemented.
* ``ready`` — implemented and covered by tests.
"""

from __future__ import annotations

from typing import Literal, TypedDict

ModuleStatus = Literal["scaffolded", "in_progress", "ready"]


class ModuleInfo(TypedDict):
    key: str
    label: str
    route: str
    phase: str
    status: ModuleStatus
    summary: str
    planned: list[str]


MODULES: tuple[ModuleInfo, ...] = (
    {
        "key": "overview",
        "label": "Overview",
        "route": "/",
        "phase": "Phase 4",
        "status": "ready",
        "summary": "Global fire activity and intelligence summary.",
        "planned": [
            "Total detections for the selected period, split by sensor",
            "Probable cross-sensor match count",
            "Daily detection trend from stored observations",
            "Global activity heatmap and top regions",
            "Data freshness panel",
        ],
    },
    {
        "key": "fire-map",
        "label": "Global Fire Map",
        "route": "/map",
        "phase": "Phase 4",
        "status": "ready",
        "summary": "Interactive global hotspot monitoring on MapLibre GL.",
        "planned": [
            "Viewport queries: gridded counts at low zoom, points when close",
            "MODIS and VIIRS layers with optional FRP density heatmap",
            "Sensor, FRP, confidence and day/night filters",
            "Hotspot inspection with full observation provenance",
            "Geographic search by country, city or coordinates",
        ],
    },
    {
        "key": "calendar",
        "label": "Burning Calendar",
        "route": "/calendar",
        "phase": "Phase 5",
        "status": "ready",
        "summary": "Historical burning activity by day, week, month and year.",
        "planned": [
            "Daily / weekly / monthly / annual buckets over stored detections",
            "Six metrics per bucket: detections, MODIS, VIIRS, FRP sum, FRP max, high confidence",
            "Bucket drill-down to the source observations with full provenance",
            "Coverage states from source availability: active, quiet, unobserved",
            "Trend (Theil–Sen), anomaly markers and a seasonal profile with sufficiency gates",
            "Seasonal climatology requires two or more years of observed months",
        ],
    },
    {
        "key": "analytics",
        "label": "Analytics",
        "route": "/analytics",
        "phase": "Phase 6",
        "status": "ready",
        "summary": "Trends, comparisons and distribution analysis.",
        "planned": [
            "Daily, weekly, monthly and annual trends",
            "Country and regional rankings",
            "FRP and confidence distributions",
            "Sensor comparisons and CSV export",
        ],
    },
    {
        "key": "harmonization",
        "label": "Sensor Intelligence",
        "route": "/harmonization",
        "phase": "Phase 3",
        "status": "ready",
        "summary": "MODIS/VIIRS normalization, matching and quality control.",
        "planned": [
            "Per-source ingestion and normalization statistics",
            "Cross-sensor association scores with full evidence",
            "Estimated fire events with clustering parameters",
            "Trace any detection back to its sensor record",
        ],
    },
    {
        "key": "anomalies",
        "label": "Anomaly Detection",
        "route": "/anomalies",
        "phase": "Phase 6",
        "status": "ready",
        "summary": "Statistical identification of unusual fire activity.",
        "planned": [
            "Seasonal baselines and MAD-based deviation scores",
            "Spatial concentration analysis",
            "Explainability panel per anomaly",
            "Alerts suppressed when historical samples are insufficient",
        ],
    },
    {
        "key": "regions",
        "label": "Regional Intelligence",
        "route": "/regions",
        "phase": "Phase 6",
        "status": "ready",
        "summary": "Regional trend, seasonality and anomaly engine over stored boundaries.",
        "planned": [
            "Country, admin-area and custom polygon selection (GeoJSON import)",
            "Radius regions and exact polygon counting without PostGIS",
            "Monthly climatology and year × month activity heatmap",
            "Mann–Kendall significance with Sen's slope and YoY change",
            "Same-month anomaly baselines and recurring-activity grid",
            "MODIS / VIIRS comparison with coverage-aware caveats",
        ],
    },
    {
        "key": "exposure",
        "label": "Exposure Analysis",
        "route": "/exposure",
        "phase": "Phase 6",
        "status": "ready",
        "summary": "Proximity of detections to settlements and infrastructure.",
        "planned": [
            "Configurable distance bands",
            "Asset categories from OSM and supporting datasets",
            "Geodesic distance with dataset attribution",
            "Labelled as geographic screening, not fire threat",
        ],
    },
    {
        "key": "reports",
        "label": "Reports",
        "route": "/reports",
        "phase": "Phase 7",
        "status": "ready",
        "summary": "Generated fire intelligence reports and exports.",
        "planned": [
            "Report templates with methodology and limitations",
            "PDF, CSV, GeoJSON and JSON export",
            "Provenance: processing versions and observation ids",
        ],
    },
    {
        "key": "assistant",
        "label": "AI Assistant",
        "route": "/assistant",
        "phase": "Phase 7",
        "status": "ready",
        "summary": "Natural-language investigation over real application data.",
        "planned": [
            "Tool-calling over approved analytical functions only",
            "Citations for periods, regions and sources",
            "No invented measurements or coordinates",
        ],
    },
    {
        "key": "cloud-readiness",
        "label": "Cloud Readiness",
        "route": "/infrastructure",
        "phase": "Phase 9",
        "status": "ready",
        "summary": "Deployment modes, Parquet datasets and verified cloud synchronisation.",
        "planned": [
            "Local, hybrid and cloud profiles from configuration",
            "Local and S3/R2 storage behind one interface",
            "Parquet export with Zstandard and per-dataset manifests",
            "Verified, resumable and allocation-aware synchronisation",
        ],
    },
    {
        "key": "settings",
        "label": "Settings",
        "route": "/settings",
        "phase": "Phase 1",
        "status": "ready",
        "summary": "System health, data sources and administration.",
        "planned": [
            "Data source registry and freshness",
            "Ingestion administration",
            "Audit log and quality reports",
        ],
    },
)

MODULES_BY_KEY: dict[str, ModuleInfo] = {module["key"]: module for module in MODULES}


def get_module(key: str) -> ModuleInfo | None:
    return MODULES_BY_KEY.get(key)
