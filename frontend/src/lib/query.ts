/** Scope shared by the data query, the calendar and the map feeds. */

export interface ObservationQuery {
  /** Exact window, ISO 8601 UTC ("2026-10-29T06:00:00Z"). */
  startAt?: string;
  endAt?: string;
  sensor?: "MODIS" | "VIIRS";
  satellite?: string;
  minFrp?: number;
  minConfidence?: "low" | "nominal" | "high";
  daynight?: "D" | "N";
  synthetic?: boolean;
  /** west,south,east,north — set when a region is chosen. */
  bbox?: [number, number, number, number];
  /** Human label for the selected region, shown as a chip. */
  region: string | null;
}

export const DEFAULT_OBSERVATION_QUERY: ObservationQuery = {
  region: null,
  synthetic: false,
};

export const SATELLITES = ["Terra", "Aqua", "Suomi-NPP", "NOAA-20", "NOAA-21"];

/** Bounding box around a gazetteer centroid; the place's zoom sets the span. */
export function bboxForPlace(
  latitude: number,
  longitude: number,
  zoom: number,
): [number, number, number, number] {
  const half = Math.min(60, Math.max(0.05, 180 / 2 ** zoom));
  const west = Math.max(-180, longitude - half);
  const east = Math.min(180, longitude + half);
  const south = Math.max(-85, latitude - half);
  const north = Math.min(85, latitude + half);
  return [
    Number(west.toFixed(4)),
    Number(south.toFixed(4)),
    Number(east.toFixed(4)),
    Number(north.toFixed(4)),
  ];
}

export function observationParams(
  query: ObservationQuery,
  extra: Record<string, string | number> = {},
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.startAt) params.set("start_at", query.startAt);
  if (query.endAt) params.set("end_at", query.endAt);
  if (query.bbox) params.set("bbox", query.bbox.map((value) => value.toFixed(4)).join(","));
  if (query.sensor) params.set("sensor", query.sensor);
  if (query.satellite) params.set("satellite", query.satellite);
  if (query.minFrp) params.set("min_frp", String(query.minFrp));
  if (query.minConfidence && query.minConfidence !== "low") {
    params.set("min_confidence", query.minConfidence);
  }
  if (query.daynight) params.set("daynight", query.daynight);
  if (query.synthetic !== undefined) params.set("synthetic", String(query.synthetic));
  for (const [key, value] of Object.entries(extra)) params.set(key, String(value));
  return params;
}

/** Same filters, same scope: the CSV is exactly the set the table shows. */
export function detectionExportUrl(params: URLSearchParams): string {
  return `/api/v1/fires/export.csv?${params.toString()}`;
}

export function activeFilterCount(query: ObservationQuery): number {
  return [
    query.startAt,
    query.endAt,
    query.sensor,
    query.satellite,
    query.minFrp,
    query.minConfidence,
    query.daynight,
    query.bbox,
    query.synthetic ? true : undefined,
  ].filter((value) => value !== undefined && value !== null && value !== "").length;
}

/** "2026-10-29T06:00" (datetime-local, read as UTC) to an API timestamp. */
export function toUtcIso(local: string): string | undefined {
  if (!local) return undefined;
  const withSeconds = local.length === 16 ? `${local}:00` : local;
  return `${withSeconds.replace(/\.\d+$/, "")}Z`;
}

/** ISO timestamp to the value a datetime-local input expects (UTC, minutes). */
export function toLocalInput(iso: string | undefined): string {
  if (!iso) return "";
  return iso.replace("Z", "").slice(0, 16);
}

/** Day bounds as a default window: 00:00 UTC to 23:59 UTC of the end date. */
export function windowForDates(startDate: string, endDate: string): { startAt: string; endAt: string } {
  return { startAt: `${startDate}T00:00:00Z`, endAt: `${endDate}T23:59:00Z` };
}

export function filterSummary(query: ObservationQuery): string {
  const parts: string[] = [];
  if (query.startAt && query.endAt) {
    const start = query.startAt.slice(0, 16).replace("T", " ");
    const end = query.endAt.slice(0, 16).replace("T", " ");
    parts.push(`${start}Z → ${end}Z`);
  }
  if (query.region) parts.push(query.region);
  parts.push(query.sensor ? `${query.sensor} only` : "MODIS + VIIRS");
  if (query.satellite) parts.push(query.satellite);
  if (query.minFrp) parts.push(`FRP ≥ ${query.minFrp} MW`);
  if (query.minConfidence && query.minConfidence !== "low") {
    parts.push(`confidence ≥ ${query.minConfidence}`);
  }
  if (query.daynight) parts.push(query.daynight === "D" ? "day only" : "night only");
  if (query.synthetic) parts.push("including synthetic fixture");
  return parts.join(" · ");
}
