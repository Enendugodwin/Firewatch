import { apiFetch } from "@/lib/api";
import type { Observation } from "@/types/api";

/** Calendar buckets always cover the full range; empty periods are explicit. */

export type CalendarGranularity = "day" | "week" | "month" | "year";
export type BucketState = "active" | "quiet" | "unobserved";

export interface BucketCoverage {
  observed: number;
  empty: number;
  missing: number;
  unknown: number;
}

export interface CalendarBucket {
  start: string;
  end: string;
  label: string;
  state: BucketState;
  coverage: BucketCoverage;
  detections: number;
  modis: number;
  viirs: number;
  frp_sum_mw: number;
  frp_max_mw: number | null;
  high_confidence: number;
}

export interface CalendarTotals {
  detections: number;
  modis: number;
  viirs: number;
  frp_sum_mw: number;
  frp_max_mw: number | null;
  high_confidence: number;
  active_buckets: number;
  quiet_buckets: number;
  unobserved_buckets: number;
  buckets: number;
}

export interface CalendarResponse {
  granularity: CalendarGranularity;
  start_date: string;
  end_date: string;
  buckets: CalendarBucket[];
  totals: CalendarTotals;
  notes: string[];
}

export interface CalendarMonthOption {
  month: string;
  start: string;
  end: string;
  detections: number;
  active_days: number;
  observed_days: number;
}

export interface CalendarDrilldown {
  bucket: CalendarBucket;
  total: number;
  returned: number;
  limit: number;
  items: Observation[];
}

export interface CalendarFilters {
  sensor?: "MODIS" | "VIIRS";
  satellite?: string;
  minFrp?: number;
  minConfidence?: "low" | "nominal" | "high";
  daynight?: "D" | "N";
  synthetic?: boolean;
  /** west,south,east,north — set by the query builder when a region is chosen. */
  bbox?: [number, number, number, number];
}

export interface CalendarQuery extends CalendarFilters {
  startDate: string;
  endDate: string;
  granularity: CalendarGranularity;
}

export type CalendarMetric = "detections" | "frp" | "high_confidence";

export const METRIC_LABEL: Record<CalendarMetric, string> = {
  detections: "Detections",
  frp: "FRP (MW)",
  high_confidence: "High-confidence detections",
};

export function metricValue(bucket: CalendarBucket, metric: CalendarMetric): number {
  if (metric === "frp") return bucket.frp_sum_mw;
  if (metric === "high_confidence") return bucket.high_confidence;
  return bucket.detections;
}

export function calendarParams(query: CalendarQuery, extra: Record<string, string | number> = {}) {
  const params = new URLSearchParams({
    start_date: query.startDate,
    end_date: query.endDate,
    granularity: query.granularity,
  });
  if (query.sensor) params.set("sensor", query.sensor);
  if (query.satellite) params.set("satellite", query.satellite);
  if (query.bbox) params.set("bbox", query.bbox.map((value) => value.toFixed(4)).join(","));
  if (query.minFrp) params.set("min_frp", String(query.minFrp));
  if (query.minConfidence && query.minConfidence !== "low") {
    params.set("min_confidence", query.minConfidence);
  }
  if (query.daynight) params.set("daynight", query.daynight);
  if (query.synthetic !== undefined) params.set("synthetic", String(query.synthetic));
  for (const [key, value] of Object.entries(extra)) params.set(key, String(value));
  return params;
}

export function fetchCalendarMonths(start: string, end: string, signal?: AbortSignal) {
  const params = new URLSearchParams({
    start_date: start,
    end_date: end,
    synthetic: "false",
  });
  return apiFetch<CalendarMonthOption[]>(`/api/v1/calendar/months?${params.toString()}`, {
    signal,
  });
}

export function fetchCalendar(query: CalendarQuery, signal?: AbortSignal) {
  return apiFetch<CalendarResponse>(`/api/v1/calendar?${calendarParams(query).toString()}`, {
    signal,
  });
}

export function fetchCalendarDrilldown(
  bucketStart: string,
  query: CalendarQuery,
  signal?: AbortSignal,
) {
  const params = calendarParams(query, { bucket_start: bucketStart, limit: 200 });
  return apiFetch<CalendarDrilldown>(
    `/api/v1/calendar/drilldown?${params.toString()}`,
    { signal },
  );
}

/** Intensity 0..1 used for cell/bar shading; robust to outliers via sqrt. */
export function intensity(value: number, max: number): number {
  if (max <= 0 || value <= 0) return 0;
  return Math.min(1, Math.sqrt(value / max));
}

/* ------------------------------------------------------------------ */
/* Fire-calendar intelligence: trend, anomalies and seasonal patterns  */
/* ------------------------------------------------------------------ */

export type TrendDirection = "rising" | "falling" | "flat" | "unknown";
export type TrendStatus = "ok" | "insufficient_history";
export type SeasonalityStatus = "ok" | "partial" | "single_year" | "insufficient_history";

export interface TrendRequirement {
  needed_observations?: number;
  available_observations?: number;
  note?: string;
  [key: string]: unknown;
}

export interface TrendPoint {
  date: string;
  value: number | null;
  observed: boolean;
  trailing_mean: number | null;
  severity: string;
}

export interface TrendBlock {
  status: TrendStatus;
  method: string;
  version: string;
  metric: string;
  observations: number;
  slope_per_day: number | null;
  slope_per_30_days: number | null;
  direction: TrendDirection;
  change_ratio: number | null;
  confidence: "low" | "medium" | "high";
  coverage: number;
  level_median?: number | null;
  flat_band_per_30_days?: number | null;
  requirements: TrendRequirement;
  series: TrendPoint[];
}

export interface SeasonMonth {
  month: number;
  label: string;
  mean: number | null;
  years: number;
  sufficient: boolean;
  index: number | null;
}

export interface SeasonalityBlock {
  status: SeasonalityStatus;
  method: string;
  version: string;
  metric: string;
  years: number[];
  years_requested: number;
  first_year: number;
  last_year: number;
  months: SeasonMonth[];
  baseline_mean: number | null;
  sufficient_months: number;
  required_months: number;
  peak_month: string | null;
  trough_month: string | null;
  seasonal_amplitude: number | null;
  requirements: {
    needed_years?: number;
    available_years?: number;
    needed_days_per_month_year?: number;
    note?: string;
    [key: string]: unknown;
  };
}

export interface CalendarAnomalyItem {
  date: string;
  observed: number;
  expected: number;
  deviation: number;
  robust_z: number | null;
  severity: string;
  explanation: string | null;
}

export interface CalendarAnomalyBlock {
  status: string | null;
  method: { name?: string; version?: string; [key: string]: unknown } | null;
  baseline: { median?: number; days?: number; [key: string]: unknown } | null;
  count: number;
  items: CalendarAnomalyItem[];
  evaluated_days: number;
  requirements: { note?: string; [key: string]: unknown } | null;
}

export interface CalendarIntelligenceWindow {
  start: string;
  end: string;
  days: number;
  observed_days: number;
  missing_days: number;
  coverage: number;
  metric: string;
  history_start: string;
}

export interface CalendarIntelligence {
  status: string;
  method: { name?: string; version?: string };
  window: CalendarIntelligenceWindow;
  trend: TrendBlock;
  anomalies: CalendarAnomalyBlock;
  seasonality: SeasonalityBlock;
  notes: string[];
}

export interface IntelligenceOptions {
  metric?: CalendarMetric;
  seasonYears?: number;
  baselineDays?: number;
}

export function fetchCalendarIntelligence(
  query: CalendarQuery,
  options: IntelligenceOptions = {},
  signal?: AbortSignal,
) {
  const params = calendarParams(query, {
    metric: options.metric ?? "detections",
    season_years: options.seasonYears ?? 5,
    baseline_days: options.baselineDays ?? 30,
  });
  params.delete("granularity");
  return apiFetch<CalendarIntelligence>(
    `/api/v1/calendar/intelligence?${params.toString()}`,
    { signal },
  );
}

