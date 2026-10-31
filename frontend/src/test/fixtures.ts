import { vi } from "vitest";

import type {
  DashboardOverview,
  FireEventOut,
  HarmonizationSummary,
  MatchPage,
  ModuleStatusItem,
  Observation,
  ObservationPage,
  SourceOut,
  SourceHealth,
  SystemStatus,
} from "@/types/api";
import type { AggregateResponse } from "@/lib/mapApi";
import type { CalendarResponse, CalendarDrilldown } from "@/lib/calendarApi";
import type { AnalyticsResponse, AnomaliesResponse } from "@/lib/analyticsApi";

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

export interface MockMap {
  cells: AggregateResponse;
  observation: Observation;
}

export interface MockQuery {
  observations: ObservationPage;
}

export interface MockCalendar {
  calendar: CalendarResponse;
  drilldown: CalendarDrilldown;
}

export interface MockOptions {
  status?: SystemStatus;
  summary?: HarmonizationSummary;
  matches?: MatchPage;
  events?: FireEventOut[];
  dashboard?: DashboardOverview;
  map?: MockMap;
  calendar?: MockCalendar;
  query?: MockQuery;
  analytics?: AnalyticsResponse;
  anomalies?: AnomaliesResponse;
}

const EMPTY_GEOMETRY = {
  type: "FeatureCollection" as const,
  features: [],
  properties: { returned: 0, total: 0, truncated: false, limit: 5000 },
};

const EMPTY_CELLS: AggregateResponse = {
  cells: [],
  cell_degrees: 11.25,
  zoom: 2,
  total_detections: 0,
  returned_cells: 0,
  truncated: false,
  bbox: [-180, -85, 180, 85],
};

const EMPTY_CALENDAR: CalendarResponse = {
  granularity: "day",
  start_date: "2026-10-29",
  end_date: "2026-10-31",
  buckets: [],
  totals: {
    detections: 0,
    modis: 0,
    viirs: 0,
    frp_sum_mw: 0,
    frp_max_mw: null,
    high_confidence: 0,
    active_buckets: 0,
    quiet_buckets: 0,
    unobserved_buckets: 0,
    buckets: 0,
  },
  notes: ["Each bucket counts thermal detections, not fires."],
};

const EMPTY_DRILLDOWN: CalendarDrilldown = {
  bucket: {
    start: "2026-10-30",
    end: "2026-10-30",
    label: "2026-10-30",
    state: "active",
    coverage: { observed: 1, empty: 0, missing: 0, unknown: 0 },
    detections: 0,
    modis: 0,
    viirs: 0,
    frp_sum_mw: 0,
    frp_max_mw: null,
    high_confidence: 0,
  },
  total: 0,
  returned: 0,
  limit: 200,
  items: [],
};

const EMPTY_ANALYTICS: AnalyticsResponse = {
  start_date: "2026-10-29",
  end_date: "2026-10-31",
  totals: {
    detections: 0,
    modis: 0,
    viirs: 0,
    frp_sum_mw: 0,
    frp_max_mw: null,
    high_confidence: 0,
    active_days: 0,
    days: 3,
    mean_daily_detections: 0,
  },
  series: [],
  top_cells: [],
  cell_degrees: 2,
  peaks: { detections: { date: null, detections: 0 }, frp: { date: null, frp_mw: null } },
  confidence: { high: 0, nominal: 0, low: 0, unknown: 0 },
  daynight: { D: 0, N: 0, unknown: 0 },
  satellites: [],
  products: [],
  synthetic_detections: 0,
  notes: ["Counts are thermal detections, not fires."],
};

const INSUFFICIENT_ANOMALIES: AnomaliesResponse = {
  status: "insufficient_history",
  method: {
    name: "robust_z",
    version: "anomaly-robust-z-v1",
    baseline_days: 30,
    min_baseline_days: 14,
    z_threshold: 3,
    metric: "detections",
    mad_to_sigma: 1.4826,
    comparison: "preceding observed days, gaps excluded",
    baseline_source: "preceding",
    min_window_days: 4,
  },
  baseline: null,
  points: [],
  anomalies: [],
  evaluated_days: 0,
  observed_baseline_days: 0,
  requirements: {
    needed_days: 14,
    available_days: 0,
    note: "Ingest more history for this scope; the engine will not score anomalies without a baseline.",
  },
  notes: ["Days without recorded source availability are excluded, not treated as zero."],
};

const PLACE_RESULTS = {
  query: "nigeria",
  count: 1,
  results: [
    {
      name: "Nigeria",
      kind: "country",
      latitude: 9.08,
      longitude: 8.68,
      iso: "NG",
      zoom: 6,
    },
  ],
  note: "Approximate centroids for map navigation.",
};

/** Install a fetch mock covering every endpoint the shell and pages use. */
export function installFetchMock(options: MockOptions = {}) {
  const status = options.status ?? makeStatus();
  const summary = options.summary ?? EMPTY_SUMMARY;
  const matches = options.matches ?? { items: [], total: 0, limit: 50, offset: 0 };
  const events = options.events ?? [];
  const dashboard = options.dashboard ?? EMPTY_DASHBOARD;
  const mapCells = options.map?.cells ?? EMPTY_CELLS;
  const mapObservation = options.map?.observation;
  const calendar = options.calendar?.calendar ?? EMPTY_CALENDAR;
  const analytics = options.analytics ?? EMPTY_ANALYTICS;
  const anomalies = options.anomalies ?? INSUFFICIENT_ANOMALIES;
  const observations: ObservationPage =
    options.query?.observations ?? { items: [], total: 0, limit: 200, offset: 0 };
  const calendarDrilldown = options.calendar?.drilldown ?? EMPTY_DRILLDOWN;

  const mock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/v1/analytics/summary")) return json(analytics);
    if (/\/api\/v1\/anomalies(\?|$)/.test(url)) return json(anomalies);
    if (url.includes("/api/v1/calendar/drilldown")) {
      // Answer for the bucket that was actually clicked, not a fixed one.
      const requested = new URL(url, "http://localhost").searchParams.get("bucket_start");
      const matching =
        calendar.buckets.find((item) => item.start === requested) ??
        calendar.buckets[0] ??
        calendarDrilldown.bucket;
      const items = matching.state === "active" ? calendarDrilldown.items : [];
      return json({
        bucket: matching,
        total: matching.detections,
        returned: items.length,
        limit: 200,
        items,
      });
    }
    if (url.includes("/api/v1/calendar")) return json(calendar);
    if (/\/api\/v1\/fires(\?|$)/.test(url)) return json(observations);
    if (url.includes("/api/v1/fires/aggregate")) return json(mapCells);
    if (url.includes("/api/v1/fires/geojson")) return json(EMPTY_GEOMETRY);
    if (url.includes("/api/v1/geo/search")) return json(PLACE_RESULTS);
    if (url.includes("/api/v1/fires/") && mapObservation) return json(mapObservation);
    if (url.includes("/api/v1/system/status")) return json(status);
    if (url.includes("/api/v1/system/modules")) return json(MODULES);
    if (url.includes("/api/v1/system/sources")) return json(SOURCES);
    if (url.includes("/api/v1/dashboard")) return json(dashboard);
    if (url.includes("/api/v1/harmonization/summary")) return json(summary);
    if (url.includes("/api/v1/harmonization/matches")) return json(matches);
    if (url.includes("/api/v1/harmonization/events")) return json(events);
    if (url.includes("/api/v1/harmonization/jobs")) return json([]);
    if (url.includes("/api/v1/admin/ingestion/run-all")) {
      return json({
        start_date: "2026-10-30",
        end_date: "2026-10-31",
        sources_requested: 2,
        sources_succeeded: 2,
        sources_failed: 0,
        records_received: 40,
        records_inserted: 40,
        records_rejected: 0,
        results: [
          {
            run_id: "run-1",
            source_code: "MODIS_NRT",
            status: "succeeded",
            records_received: 20,
            records_inserted: 20,
            records_rejected: 0,
            partitions_completed: 1,
            partitions_skipped: 0,
            rejections: {},
            errors: [],
            is_synthetic: false,
            harmonization: null,
            events: null,
          },
          {
            run_id: "run-2",
            source_code: "VIIRS_SNPP_NRT",
            status: "succeeded",
            records_received: 20,
            records_inserted: 20,
            records_rejected: 0,
            partitions_completed: 1,
            partitions_skipped: 0,
            rejections: {},
            errors: [],
            is_synthetic: false,
            harmonization: null,
            events: null,
          },
        ],
        harmonization: null,
        events: null,
      });
    }
    if (url.includes("/api/v1/admin/ingestion/jobs")) return json([]);
    if (url.includes("/api/v1/admin/ingestion/sources")) return json(SOURCE_HEALTH);
    return json({ error: { code: "not_found", message: "unmocked", details: {} } }, 404);
  });

  vi.stubGlobal("fetch", mock);
  return mock;
}
