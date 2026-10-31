import { vi } from "vitest";

import type {
  DashboardOverview,
  FireEventOut,
  HarmonizationSummary,
  MatchPage,
  ModuleStatusItem,
  SourceOut,
  SourceHealth,
  SystemStatus,
} from "@/types/api";

export const MODULES: ModuleStatusItem[] = [
  {
    key: "overview",
    label: "Overview",
    route: "/",
    phase: "Phase 4",
    status: "in_progress",
    summary: "Global fire activity and intelligence summary.",
    planned: ["Detections split by sensor", "Daily detection trend"],
  },
  {
    key: "harmonization",
    label: "Sensor Intelligence",
    route: "/harmonization",
    phase: "Phase 3",
    status: "ready",
    summary: "MODIS/VIIRS normalization, matching and quality control.",
    planned: ["Cross-sensor association scores with full evidence"],
  },
  {
    key: "calendar",
    label: "Burning Calendar",
    route: "/calendar",
    phase: "Phase 5",
    status: "scaffolded",
    summary: "Historical burning activity by day, month and year.",
    planned: ["Daily / weekly / monthly / annual views"],
  },
  {
    key: "settings",
    label: "Settings",
    route: "/settings",
    phase: "Phase 1",
    status: "in_progress",
    summary: "System health, data sources and administration.",
    planned: ["Data source registry and freshness"],
  },
];

export function makeStatus(overrides: Partial<SystemStatus["data"]> = {}): SystemStatus {
  return {
    app_name: "FIREWATCH X",
    app_version: "0.1.0",
    environment: "test",
    phase: "3",
    phase_name: "Harmonization",
    server_time: "2026-10-30T00:00:00Z",
    uptime_seconds: 42,
    database: { dialect: "sqlite", connected: true, postgis: null, latency_ms: 1.2, error: null },
    data: {
      freshness: "no_data",
      freshness_reason:
        "FIRMS_MAP_KEY is not configured, so no NASA observations can be retrieved.",
      firms_configured: false,
      sources_registered: 8,
      observations_stored: 0,
      synthetic_observations: 0,
      missing_dates: 0,
      last_ingested_at: null,
      last_observation_at: null,
      ...overrides,
    },
    capabilities: {
      authentication: false,
      rate_limiting: false,
      ai_assistant: false,
      reports: false,
      ingestion: false,
      spatial: false,
    },
    modules: MODULES,
  };
}

export const SOURCES: SourceOut[] = [
  {
    code: "MODIS_SP",
    sensor: "MODIS",
    satellite: "Terra/Aqua",
    processing_level: "SP",
    description: "MODIS standard processing.",
    status: "not_ingested",
    observations: 0,
    last_observation_at: null,
  },
];

export const SOURCE_HEALTH: SourceHealth[] = [
  {
    code: "MODIS_SP",
    sensor: "MODIS",
    satellite: "Terra/Aqua",
    processing_level: "SP",
    registered: true,
    observations: 0,
    last_run_status: null,
    last_run_at: null,
    last_error: null,
  },
];

export const EMPTY_DASHBOARD: DashboardOverview = {
  period: { start_date: null, end_date: null },
  detections: { total: 0, modis: 0, viirs: 0, frp_mw: 0 },
  matches: { total: 0, probable: 0, possible: 0 },
  events: 0,
  scope: null,
  data: makeStatus().data,
  note: "Counts are satellite thermal detections, not the number of fires.",
};

export const EMPTY_SUMMARY: HarmonizationSummary = {
  observations: 0,
  modis_observations: 0,
  viirs_observations: 0,
  synthetic_observations: 0,
  matches_total: 0,
  matches_probable: 0,
  matches_possible: 0,
  matches_rejected: 0,
  events: 0,
  multi_sensor_events: 0,
  last_run_at: null,
  last_run_status: null,
  parameters: {},
  last_run_scope: null,
  algorithm_version: "assoc-v1",
};

export const FIXTURE_SUMMARY: HarmonizationSummary = {
  ...EMPTY_SUMMARY,
  observations: 9,
  modis_observations: 5,
  viirs_observations: 4,
  synthetic_observations: 9,
  matches_total: 5,
  matches_probable: 1,
  matches_possible: 2,
  matches_rejected: 2,
  events: 2,
  multi_sensor_events: 2,
  last_run_at: "2026-10-30T12:00:00Z",
  last_run_status: "succeeded",
  last_run_scope: { bbox: [2.5, 4, 14.7, 13.9], start_date: "2026-10-29", end_date: "2026-10-30" },
};

export const MATCHES: MatchPage = {
  total: 1,
  limit: 50,
  offset: 0,
  items: [
    {
      id: "match-1",
      observation_a: {
        id: "obs-a",
        source_code: "MODIS_SP",
        sensor: "MODIS",
        satellite: "Terra",
        latitude: 8.5,
        longitude: 9.1,
        acquired_at: "2026-10-28T10:20:00Z",
        confidence_category: "high",
        frp_mw: 12.4,
      },
      observation_b: {
        id: "obs-b",
        source_code: "VIIRS_SNPP_SP",
        sensor: "VIIRS",
        satellite: "Suomi-NPP",
        latitude: 8.503,
        longitude: 9.104,
        acquired_at: "2026-10-28T10:35:00Z",
        confidence_category: "high",
        frp_mw: 9.8,
      },
      temporal_delta_seconds: 900,
      spatial_distance_m: 420.5,
      footprint_overlap: 0.72,
      association_score: 0.912,
      match_status: "probable",
      components: {
        temporal_similarity: 0.9167,
        spatial_proximity: 0.7897,
        footprint_overlap: 0.72,
        weights: { temporal: 0.4, spatial: 0.45, footprint: 0.15 },
        weight_note: "weights renormalised over available components",
      },
      algorithm_version: "assoc-v1",
      created_at: "2026-10-30T12:00:00Z",
    },
  ],
};

export const EVENTS: FireEventOut[] = [
  {
    id: "event-1",
    first_detected_at: "2026-10-28T10:20:00Z",
    last_detected_at: "2026-10-28T11:25:00Z",
    centroid_latitude: 8.5033,
    centroid_longitude: 9.0985,
    min_latitude: 8.498,
    max_latitude: 8.512,
    min_longitude: 9.093,
    max_longitude: 9.104,
    observation_count: 4,
    sensor_count: 2,
    maximum_frp_mw: 12.4,
    aggregate_frp_mw: 35.6,
    clustering_method: "dbscan_spatiotemporal",
    clustering_parameters: { eps_meters: 1500, eps_hours: 24, min_samples: 2 },
    methodology_version: "events-v1",
  },
];

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export interface MockOptions {
  status?: SystemStatus;
  summary?: HarmonizationSummary;
  matches?: MatchPage;
  events?: FireEventOut[];
  dashboard?: DashboardOverview;
}

/** Install a fetch mock covering every endpoint the shell and pages use. */
export function installFetchMock(options: MockOptions = {}) {
  const status = options.status ?? makeStatus();
  const summary = options.summary ?? EMPTY_SUMMARY;
  const matches = options.matches ?? { items: [], total: 0, limit: 50, offset: 0 };
  const events = options.events ?? [];
  const dashboard = options.dashboard ?? EMPTY_DASHBOARD;

  const mock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/v1/system/status")) return json(status);
    if (url.includes("/api/v1/system/modules")) return json(MODULES);
    if (url.includes("/api/v1/system/sources")) return json(SOURCES);
    if (url.includes("/api/v1/dashboard")) return json(dashboard);
    if (url.includes("/api/v1/harmonization/summary")) return json(summary);
    if (url.includes("/api/v1/harmonization/matches")) return json(matches);
    if (url.includes("/api/v1/harmonization/events")) return json(events);
    if (url.includes("/api/v1/harmonization/jobs")) return json([]);
    if (url.includes("/api/v1/admin/ingestion/jobs")) return json([]);
    if (url.includes("/api/v1/admin/ingestion/sources")) return json(SOURCE_HEALTH);
    return json({ error: { code: "not_found", message: "unmocked", details: {} } }, 404);
  });

  vi.stubGlobal("fetch", mock);
  return mock;
}
