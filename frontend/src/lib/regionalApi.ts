import { apiFetch } from "@/lib/api";

/**
 * Regional intelligence API.
 *
 * Reads are served from the materialised regional statistics; only `analyze`
 * touches the observation table. A region that has not been analysed returns
 * `status: "not_analyzed"` rather than a zero.
 */

export type RegionLevel = "country" | "state" | "province" | "custom" | "radius" | string;
export type RegionalSensor = "ALL" | "MODIS" | "VIIRS";

export interface GeographicRegion {
  id: string;
  slug: string;
  name: string;
  level: RegionLevel;
  boundary_kind: string;
  bbox: [number, number, number, number];
  area_km2: number | null;
  vertices: number;
  boundary_version: string;
  source: string;
  is_approximate: boolean;
  notes: string | null;
  last_analyzed_at: string | null;
  last_analysis_algorithm: string | null;
  grid_degrees: number;
}

export interface RegionCatalog {
  regions: GeographicRegion[];
  total: number;
  note: string;
}

export interface NotAnalyzed {
  status: "not_analyzed";
  region: GeographicRegion;
  window: { start: string; end: string; sensor?: string };
  requirements: { note: string };
}

export interface AnalyzeResult {
  status: string;
  region_id: string;
  window: { start: string; end: string };
  sensors: string[];
  synthetic: boolean;
  scanned_candidates: number;
  detections_in_region: number;
  days_covered: number;
  days_requested: number;
  rows_written: number;
  cells: number;
  algorithm_version: string;
  notes: string[];
}

export interface RegionalTotals {
  detections: number;
  frp_sum_mw: number;
  frp_max_mw: number | null;
  high_confidence: number;
  active_days: number;
  covered_days: number;
  requested_days: number;
  coverage: number;
}

export interface RegionOverview {
  status: "ok";
  region: GeographicRegion;
  window: { start: string; end: string; sensor: string };
  totals: RegionalTotals;
  peak_month: { month: number; mean_detections: number; years: number } | null;
  trend: {
    status: string;
    direction: string;
    p_value: number | null;
    sen_slope_per_year: number | null;
    complete_years: number;
    note: string;
  };
  anomalies: { status: string; count: number; evaluated_months: number };
  current_month: {
    year: number;
    month: number;
    observed: number | null;
    median: number | null;
    deviation_ratio: number | null;
    baseline_years: number;
    status: "ok" | "insufficient_history" | "no_current_data";
    coverage?: number;
    note: string;
  };
  sensor_note: string;
  notes: string[];
}

export interface MonthPoint {
  year: number;
  month: number;
  detections: number;
  frp_sum_mw: number;
  frp_max_mw: number | null;
  high_confidence: number;
  covered_days: number;
  active_days: number;
  days_in_month: number;
  expected_days: number;
  coverage: number;
}

export interface YearPoint {
  year: number;
  detections: number;
  frp_sum_mw: number;
  frp_max_mw: number | null;
  high_confidence: number;
  covered_days: number;
  active_days: number;
  days_in_year: number;
  coverage: number;
  complete: boolean;
  yoy_change: number | null;
}

export interface SeasonMonth {
  month: number;
  mean: number | null;
  median: number | null;
  p90: number | null;
  years: number;
  sufficient: boolean;
  index: number | null;
}

export interface SeasonalityReport {
  status: "ok" | "partial" | "single_year" | "insufficient_history";
  region: GeographicRegion;
  window: { start: string; end: string; sensor: string };
  method: string;
  version: string;
  years: number[];
  months: SeasonMonth[];
  peak_month: number | null;
  trough_month: number | null;
  seasonal_amplitude: number | null;
  sufficient_months: number;
  required_months: number;
  day_of_year: {
    smoothing_days: number;
    coverage: string;
    points: Array<{ day_of_year: number; mean: number | null; samples: number; years: number }>;
  };
  requirements: { needed_years: number; available_years: number; note: string };
}

export interface MannKendall {
  status: string;
  n: number;
  s: number | null;
  z: number | null;
  p_value: number | null;
  trend: string;
  sen_slope_per_year: number | null;
  sen_slope_per_decade: number | null;
  serial_correlation: number | null;
}

export interface TrendsReport {
  status: "ok" | "insufficient_years";
  region: GeographicRegion;
  window: { start: string; end: string; sensor: string };
  annual: Array<{ year: number; detections: number; complete: boolean; coverage: number }>;
  yoy: Array<{ year: number; change: number | null }>;
  rolling: Record<string, Array<{ date: string; mean: number; days: number }>>;
  mann_kendall: MannKendall;
  significant: boolean;
  seasonal_trends: Array<{
    month: number;
    years: number;
    trend: string;
    p_value: number | null;
    sen_slope_per_year: number | null;
  }>;
  requirements: { needed_years: number; available_complete_years: number; note: string };
  caveats: string[];
}

export interface RegionAnomaly {
  period: string;
  year: number;
  month: number;
  observed: number;
  expected_median: number;
  mad: number;
  scale: number;
  deviation_ratio: number | null;
  robust_z: number | null;
  severity: string;
  baseline_years: number;
  method: string;
  version: string;
}

export interface AnomaliesReport {
  status: "ok" | "insufficient_history";
  region: GeographicRegion;
  window: { start: string; end: string; sensor: string };
  evaluated_months: number;
  count: number;
  anomalies: RegionAnomaly[];
  requirements: { needed_baseline_years: number; note: string };
  notes: string[];
}

export interface SpatialCell {
  lat_index: number;
  lon_index: number;
  latitude: number;
  longitude: number;
  detections: number;
  frp_sum_mw: number;
  frp_max_mw: number | null;
  years_with_detections: number;
  recurrence: number;
  first_year: number | null;
  last_year: number | null;
}

export interface SpatialReport {
  status: "ok" | "not_analyzed";
  region: GeographicRegion;
  grid_degrees: number;
  cells: SpatialCell[];
  returned: number;
  notes: string[];
  requirements?: { note: string };
}

export interface SensorComparison {
  status: "ok" | "single_sensor" | "not_analyzed";
  region: GeographicRegion;
  window: { start: string; end: string };
  sensors: Record<
    string,
    {
      detections: number;
      active_days: number;
      covered_days: number;
      first_date: string;
      last_date: string;
    }
  >;
  correlation: { pearson_r: number; months: number; method: string } | null;
  notes: string[];
  requirements: { note: string };
}

export interface MonthlyReport {
  status: "ok" | "not_analyzed";
  region: GeographicRegion;
  window: { start: string; end: string; sensor: string };
  months: MonthPoint[];
  notes: string[];
}

export interface YearlyReport {
  status: "ok" | "not_analyzed";
  region: GeographicRegion;
  window: { start: string; end: string; sensor: string };
  years: YearPoint[];
  notes: string[];
}

function rangeParams(start: string, end: string, sensor: RegionalSensor) {
  return new URLSearchParams({ start_date: start, end_date: end, sensor });
}

export function fetchRegionCatalog(signal?: AbortSignal) {
  return apiFetch<RegionCatalog>("/api/v1/regions/catalog?limit=500", { signal });
}

export function fetchRegionOverview(
  id: string,
  start: string,
  end: string,
  sensor: RegionalSensor,
  signal?: AbortSignal,
) {
  return apiFetch<RegionOverview | NotAnalyzed>(
    `/api/v1/regions/${id}/overview?${rangeParams(start, end, sensor)}`,
    { signal },
  );
}

export function fetchRegionMonthly(
  id: string,
  start: string,
  end: string,
  sensor: RegionalSensor,
  signal?: AbortSignal,
) {
  return apiFetch<MonthlyReport | NotAnalyzed>(
    `/api/v1/regions/${id}/monthly?${rangeParams(start, end, sensor)}`,
    { signal },
  );
}

export function fetchRegionYearly(
  id: string,
  start: string,
  end: string,
  sensor: RegionalSensor,
  signal?: AbortSignal,
) {
  return apiFetch<YearlyReport | NotAnalyzed>(
    `/api/v1/regions/${id}/yearly?${rangeParams(start, end, sensor)}`,
    { signal },
  );
}

export function fetchRegionSeasonality(
  id: string,
  start: string,
  end: string,
  sensor: RegionalSensor,
  signal?: AbortSignal,
) {
  return apiFetch<SeasonalityReport | NotAnalyzed>(
    `/api/v1/regions/${id}/seasonality?${rangeParams(start, end, sensor)}`,
    { signal },
  );
}

export function fetchRegionTrends(
  id: string,
  start: string,
  end: string,
  sensor: RegionalSensor,
  signal?: AbortSignal,
) {
  return apiFetch<TrendsReport | NotAnalyzed>(
    `/api/v1/regions/${id}/trends?${rangeParams(start, end, sensor)}`,
    { signal },
  );
}

export function fetchRegionAnomalies(
  id: string,
  start: string,
  end: string,
  sensor: RegionalSensor,
  signal?: AbortSignal,
) {
  return apiFetch<AnomaliesReport | NotAnalyzed>(
    `/api/v1/regions/${id}/anomalies?${rangeParams(start, end, sensor)}`,
    { signal },
  );
}

export function fetchRegionSpatial(id: string, signal?: AbortSignal) {
  return apiFetch<SpatialReport>(`/api/v1/regions/${id}/spatial-activity?limit=40`, {
    signal,
  });
}

export function fetchRegionSensors(
  id: string,
  start: string,
  end: string,
  signal?: AbortSignal,
) {
  return apiFetch<SensorComparison | NotAnalyzed>(
    `/api/v1/regions/${id}/sensor-comparison?start_date=${start}&end_date=${end}`,
    { signal },
  );
}

export function analyzeRegion(
  id: string,
  body: { start_date: string; end_date: string; synthetic?: boolean; sensor?: "MODIS" | "VIIRS" },
) {
  return apiFetch<AnalyzeResult>(`/api/v1/regions/${id}/analyze`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function regionExportUrl(id: string, start: string, end: string, sensor: RegionalSensor) {
  return `/api/v1/regions/${id}/export?${rangeParams(start, end, sensor)}`;
}
