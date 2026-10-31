import { apiFetch } from "@/lib/api";

/** Server-computed analytics and anomaly results. */

export interface AnalyticsTotals {
  detections: number;
  modis: number;
  viirs: number;
  frp_sum_mw: number;
  frp_max_mw: number | null;
  high_confidence: number;
  active_days: number;
  days: number;
  mean_daily_detections: number;
}

export interface DailyPoint {
  date: string;
  detections: number;
  modis: number;
  viirs: number;
  frp_sum_mw: number;
}

export interface TopCell {
  latitude: number;
  longitude: number;
  detections: number;
  frp_sum_mw: number;
  frp_max_mw: number | null;
}

export interface AnalyticsResponse {
  start_date: string;
  end_date: string;
  totals: AnalyticsTotals;
  series: DailyPoint[];
  top_cells: TopCell[];
  cell_degrees: number;
  peaks: {
    detections: { date: string | null; detections: number };
    frp: { date: string | null; frp_mw: number | null };
  };
  confidence: Record<string, number>;
  daynight: Record<string, number>;
  satellites: Array<{ satellite: string; detections: number; frp_sum_mw: number }>;
  products: Array<{ source_code: string; detections: number }>;
  synthetic_detections: number;
  notes: string[];
}

export type AnomalySeverity =
  | "normal"
  | "below_baseline"
  | "moderate"
  | "high"
  | "critical"
  | "unknown_scale";

export interface AnomalyPoint {
  date: string;
  observed: number;
  expected: number;
  deviation: number;
  robust_z: number | null;
  severity: AnomalySeverity;
  explanation: string | null;
}

export interface AnomaliesResponse {
  status: "ok" | "insufficient_history";
  method: {
    name: string;
    version: string;
    baseline_days: number;
    min_baseline_days: number;
    z_threshold: number;
    metric: string;
    mad_to_sigma: number;
    comparison: string;
    baseline_source: "preceding" | "within_window";
    min_window_days: number;
  };
  baseline: { days: number; median: number; mad: number; scale: number } | null;
  points: AnomalyPoint[];
  anomalies: AnomalyPoint[];
  evaluated_days: number;
  observed_baseline_days: number;
  requirements: { needed_days: number; available_days: number; note: string };
  notes: string[];
}

export function fetchAnalytics(startDate: string, endDate: string, signal?: AbortSignal) {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
    synthetic: "false",
    top: "10",
  });
  return apiFetch<AnalyticsResponse>(`/api/v1/analytics/summary?${params.toString()}`, { signal });
}

export function fetchAnomalies(startDate: string, endDate: string, signal?: AbortSignal) {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
    synthetic: "false",
  });
  return apiFetch<AnomaliesResponse>(`/api/v1/anomalies?${params.toString()}`, { signal });
}

/** Relative bar width for the daily trend, guarded against an all-zero series. */
export function trendBars(series: DailyPoint[]): Array<DailyPoint & { ratio: number }> {
  const max = series.reduce((peak, point) => Math.max(peak, point.detections), 0);
  return series.map((point) => ({
    ...point,
    ratio: max > 0 ? point.detections / max : 0,
  }));
}
