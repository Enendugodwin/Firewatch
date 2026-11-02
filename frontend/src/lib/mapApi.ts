import { apiFetch } from "@/lib/api";
import type { Observation } from "@/types/api";

/** Map viewport in [west, south, east, north]. */
export type Bounds = [number, number, number, number];

export interface FireCell {
  longitude: number;
  latitude: number;
  count: number;
  modis: number;
  viirs: number;
  max_frp_mw: number | null;
  latest_acquired_at: string | null;
}

export interface AggregateResponse {
  cells: FireCell[];
  cell_degrees: number;
  requested_cell_degrees?: number;
  source?: "rollup" | "live" | string;
  note?: string | null;
  zoom: number;
  total_detections: number;
  returned_cells: number;
  truncated: boolean;
  bbox: number[];
}

export interface FireFeatureProperties {
  id: string;
  sensor: string;
  satellite: string;
  acquired_at: string;
  confidence: string | null;
  frp_mw: number | null;
  daynight: string | null;
  source: string;
  synthetic: boolean;
}

export interface FireFeature {
  type: "Feature";
  id: string;
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: FireFeatureProperties;
}

export interface FireFeatureCollection {
  type: "FeatureCollection";
  features: FireFeature[];
  properties: {
    returned: number;
    total: number;
    truncated: boolean;
    limit: number;
  };
}

export interface GeoPlace {
  name: string;
  kind: "country" | "city" | "coordinates";
  latitude: number;
  longitude: number;
  iso: string | null;
  zoom: number;
}

export interface GeoSearchResponse {
  query: string;
  count: number;
  results: GeoPlace[];
  note: string;
}

export interface FireQuery {
  bbox: Bounds;
  sensor?: "MODIS" | "VIIRS";
  minFrp?: number;
  daynight?: "D" | "N";
  minConfidence?: "low" | "nominal" | "high";
  synthetic?: boolean;
  startDate?: string;
  endDate?: string;
}

export function fireQueryParams(query: FireQuery, extra: Record<string, string | number> = {}) {
  const params = new URLSearchParams({
    bbox: query.bbox.map((value) => value.toFixed(5)).join(","),
  });
  if (query.sensor) params.set("sensor", query.sensor);
  if (query.minFrp) params.set("min_frp", String(query.minFrp));
  if (query.daynight) params.set("daynight", query.daynight);
  if (query.minConfidence && query.minConfidence !== "low") {
    params.set("min_confidence", query.minConfidence);
  }
  if (query.synthetic !== undefined) params.set("synthetic", String(query.synthetic));
  if (query.startDate) params.set("start_date", query.startDate);
  if (query.endDate) params.set("end_date", query.endDate);
  for (const [key, value] of Object.entries(extra)) params.set(key, String(value));
  return params;
}

export function fetchAggregate(query: FireQuery, zoom: number, signal?: AbortSignal) {
  const params = fireQueryParams(query, { zoom: Math.round(zoom) });
  return apiFetch<AggregateResponse>(`/api/v1/fires/aggregate?${params.toString()}`, { signal });
}

export function fetchFireFeatures(
  query: FireQuery,
  limit: number,
  signal?: AbortSignal,
) {
  const params = fireQueryParams(query, { limit });
  return apiFetch<FireFeatureCollection>(`/api/v1/fires/geojson?${params.toString()}`, {
    signal,
  });
}

export function fetchObservation(id: string, signal?: AbortSignal) {
  return apiFetch<Observation>(`/api/v1/fires/${id}`, { signal });
}

export function searchPlaces(term: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ q: term, limit: "6" });
  return apiFetch<GeoSearchResponse>(`/api/v1/geo/search?${params.toString()}`, { signal });
}
