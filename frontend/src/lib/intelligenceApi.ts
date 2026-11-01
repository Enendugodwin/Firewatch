import { apiFetch } from "@/lib/api";

export interface ReportResponse {
  version: string;
  start_date: string;
  end_date: string;
  headline: {
    detections: number;
    active_days: number;
    days: number;
    frp_sum_mw: number;
    frp_max_mw: number | null;
    high_confidence: number;
    modis: number;
    viirs: number;
  };
  series: Array<{ date: string; detections: number; frp_sum_mw: number }>;
  top_cells: Array<{ latitude: number; longitude: number; detections: number }>;
  harmonization: {
    matches_total: number;
    probable: number;
    events: number;
    multi_sensor_events: number;
    note: string;
  };
  anomalies: { status: string; flagged: unknown[]; method: string; baseline_source: string };
  coverage: { days_with_detections: number; range_days: number; synthetic_rows: number };
  notes: string[];
}

export interface RegionProfile {
  name: string;
  iso: string | null;
  latitude: number;
  longitude: number;
  bbox: number[];
  detections: number;
  frp_sum_mw: number;
  frp_max_mw: number | null;
  active_days: number;
}

export interface RegionsResponse {
  regions: RegionProfile[];
  note: string;
  half_degrees: number;
}

export interface WatchedAsset {
  id: string;
  name: string;
  category: string;
  latitude: number;
  longitude: number;
}

export interface ExposureScreen {
  assets: Array<{
    asset_id: string;
    name: string;
    category: string;
    latitude: number;
    longitude: number;
    detections_within_radius: number;
    frp_sum_mw: number;
    frp_max_mw: number | null;
    nearest: {
      distance_km: number;
      latitude: number;
      longitude: number;
      acquired_at: string;
      frp_mw: number | null;
      sensor: string;
    } | null;
  }>;
  asset_count: number;
  radius_km: number;
  observations_scanned: number;
  truncated: boolean;
  note: string;
}

export interface AssistantReply {
  answer: string;
  intent: string;
  scope: { start_date: string; end_date: string; place: string | null; bbox: number[] | null };
  data: Record<string, unknown>;
  method: string;
  capabilities: string[];
  notes: string[];
}

const range = (start: string, end: string) => `start_date=${start}&end_date=${end}`;

export function fetchReport(start: string, end: string, signal?: AbortSignal) {
  return apiFetch<ReportResponse>(`/api/v1/reports/summary?${range(start, end)}`, { signal });
}

export function reportExportUrl(start: string, end: string, format: "markdown" | "json") {
  return `/api/v1/reports/export?${range(start, end)}&format=${format}`;
}

export function fetchRegions(start: string, end: string, signal?: AbortSignal) {
  return apiFetch<RegionsResponse>(
    `/api/v1/regions?${range(start, end)}&limit=10`,
    { signal },
  );
}

export function fetchAssets(signal?: AbortSignal) {
  return apiFetch<WatchedAsset[]>("/api/v1/exposure/assets", { signal });
}

export function addAsset(payload: {
  name: string;
  latitude: number;
  longitude: number;
  category?: string;
}) {
  return apiFetch<WatchedAsset>("/api/v1/exposure/assets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function removeAsset(id: string) {
  return apiFetch<void>(`/api/v1/exposure/assets/${id}`, { method: "DELETE" });
}

export function fetchScreen(start: string, end: string, signal?: AbortSignal) {
  return apiFetch<ExposureScreen>(
    `/api/v1/exposure/screen?${range(start, end)}&radius_km=50`,
    { signal },
  );
}

export function askAssistant(question: string, start: string, end: string) {
  return apiFetch<AssistantReply>("/api/v1/assistant/chat", {
    method: "POST",
    body: JSON.stringify({ question, start_date: start, end_date: end }),
  });
}
