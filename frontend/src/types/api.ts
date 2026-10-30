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
  status: "not_ingested" | "ingesting" | "ok" | "error";
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    request_id: string | null;
  };
}
