/** Types mirroring the FastAPI response models (backend/app/schemas). */

export type ModuleStatus = "scaffolded" | "in_progress" | "ready";

export type FreshnessState = "no_data" | "stale" | "delayed" | "current" | "unknown";

export interface DatabaseStatus {
  dialect: string;
  connected: boolean;
  postgis: boolean | null;
  latency_ms: number | null;
  error: string | null;
}

export interface DataStatus {
  freshness: FreshnessState;
  freshness_reason: string;
  firms_configured: boolean;
  sources_registered: number;
  observations_stored: number | null;
  synthetic_observations: number;
  missing_dates: number;
  last_ingested_at: string | null;
  last_observation_at: string | null;
}

export interface CapabilityStatus {
  authentication: boolean;
  rate_limiting: boolean;
  ai_assistant: boolean;
  reports: boolean;
  ingestion: boolean;
  spatial: boolean;
}

export interface ModuleStatusItem {
  key: string;
  label: string;
  route: string;
  phase: string;
  status: ModuleStatus;
  summary: string;
  planned: string[];
}

export interface SystemStatus {
  app_name: string;
  app_version: string;
  environment: string;
  phase: string;
  phase_name: string;
  server_time: string;
  uptime_seconds: number;
  database: DatabaseStatus;
  data: DataStatus;
  capabilities: CapabilityStatus;
  modules: ModuleStatusItem[];
}

export interface SourceOut {
  code: string;
  sensor: "MODIS" | "VIIRS";
  satellite: string;
  processing_level: "SP" | "NRT";
  description: string;
  status: "not_ingested" | "ok" | "error";
  observations: number;
  last_observation_at: string | null;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    request_id: string | null;
  };
}

/* --- observations ------------------------------------------------------- */

export interface Observation {
  id: string;
  source_code: string;
  source_record_id: string;
  sensor: "MODIS" | "VIIRS";
  satellite: string;
  latitude: number;
  longitude: number;
  acquired_at: string;
  confidence_raw: number | null;
  confidence_category: string | null;
  brightness_temperature: number | null;
  brightness_channel: string | null;
  frp_mw: number | null;
  scan_km: number | null;
  track_km: number | null;
  daynight: string | null;
  processing_version: string | null;
  source_product: string;
  quality_flags: Record<string, unknown>;
  is_synthetic: boolean;
}

export interface ObservationPage {
  items: Observation[];
  total: number;
  limit: number;
  offset: number;
}

/* --- harmonization ------------------------------------------------------ */

export type MatchStatus = "probable" | "possible" | "rejected";

export interface ObservationBrief {
  id: string;
  source_code: string;
  sensor: string;
  satellite: string;
  latitude: number;
  longitude: number;
  acquired_at: string;
  confidence_category: string | null;
  frp_mw: number | null;
}

export interface MatchComponents {
  temporal_similarity?: number;
  spatial_proximity?: number;
  footprint_overlap?: number | null;
  weights?: Record<string, number>;
  weight_note?: string;
}

export interface ObservationMatch {
  id: string;
  observation_a: ObservationBrief;
  observation_b: ObservationBrief;
  temporal_delta_seconds: number;
  spatial_distance_m: number;
  footprint_overlap: number | null;
  association_score: number;
  match_status: MatchStatus;
  components: MatchComponents;
  algorithm_version: string;
  created_at: string;
}

export interface MatchPage {
  items: ObservationMatch[];
  total: number;
  limit: number;
  offset: number;
}

export interface FireEventOut {
  id: string;
  first_detected_at: string;
  last_detected_at: string;
  centroid_latitude: number;
  centroid_longitude: number;
  min_latitude: number;
  max_latitude: number;
  min_longitude: number;
  max_longitude: number;
  observation_count: number;
  sensor_count: number;
  maximum_frp_mw: number | null;
  aggregate_frp_mw: number | null;
  clustering_method: string;
  clustering_parameters: Record<string, number>;
  methodology_version: string;
}

export interface HarmonizationSummary {
  observations: number;
  modis_observations: number;
  viirs_observations: number;
  synthetic_observations: number;
  matches_total: number;
  matches_probable: number;
  matches_possible: number;
  matches_rejected: number;
  events: number;
  multi_sensor_events: number;
  last_run_at: string | null;
  last_run_status: string | null;
  parameters: Record<string, unknown>;
  last_run_scope: {
    bbox?: number[] | null;
    start_date?: string | null;
    end_date?: string | null;
  } | null;
  algorithm_version: string;
}

export interface AlgorithmRunOut {
  id: string;
  kind: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  parameters: Record<string, unknown>;
  stats: Record<string, unknown>;
  algorithm_version: string;
  is_synthetic: boolean;
  error_message: string | null;
}

/* --- dashboard / ingestion --------------------------------------------- */

export interface DashboardOverview {
  period: { start_date: string | null; end_date: string | null };
  detections: { total: number; modis: number; viirs: number; frp_mw: number };
  matches: { total: number; probable: number; possible: number };
  events: number;
  scope: {
    bbox?: number[] | null;
    start_date?: string | null;
    end_date?: string | null;
  } | null;
  data: DataStatus;
  note: string;
}

export interface IngestionRunOut {
  id: string;
  source_code: string | null;
  status: string;
  started_at: string;
  completed_at: string | null;
  records_received: number;
  records_inserted: number;
  records_rejected: number;
  is_synthetic: boolean;
  error_message: string | null;
  query_parameters: Record<string, unknown>;
}

export interface SourceHealth {
  code: string;
  sensor: string;
  satellite: string;
  processing_level: string;
  registered: boolean;
  observations: number;
  last_run_status: string | null;
  last_run_at: string | null;
  last_error: string | null;
}

export interface IngestAllResponse {
  start_date: string;
  end_date: string;
  sources_requested: number;
  sources_succeeded: number;
  sources_failed: number;
  records_received: number;
  records_inserted: number;
  records_rejected: number;
  results: IngestResponse[];
  harmonization: Record<string, unknown> | null;
  events: Record<string, unknown> | null;
}

export interface IngestResponse {
  run_id: string | null;
  source_code: string;
  status: string;
  records_received: number;
  records_inserted: number;
  records_rejected: number;
  partitions_completed: number;
  partitions_skipped: number;
  rejections: Record<string, number>;
  errors: string[];
  is_synthetic: boolean;
  harmonization: Record<string, unknown> | null;
  events: Record<string, unknown> | null;
}
