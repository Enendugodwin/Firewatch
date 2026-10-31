import type { FireFeature, FireFeatureCollection, FireCell } from "@/lib/mapApi";
import type { Observation } from "@/types/api";

/**
 * Map layer definitions and pure helpers. Kept free of MapLibre instances so the
 * expressions and conversions can be unit-tested without WebGL.
 */

/** Below this zoom the map requests gridded counts instead of individual points. */
export const AGGREGATE_ZOOM = 6;
/** Upper bound for a single point request; above it the server truncates. */
export const POINT_LIMIT = 5000;

export const FIRE_COLORS = {
  low: "#FACC15",
  medium: "#FB923C",
  high: "#EF4444",
} as const;

export const SENSOR_COLORS = {
  MODIS: "#72A5F9",
  VIIRS: "#60D58B",
} as const;

export function useAggregate(zoom: number): boolean {
  return zoom < AGGREGATE_ZOOM;
}

export function frpColorExpression(): unknown[] {
  return [
    "step",
    ["coalesce", ["get", "frp_mw"], 0],
    FIRE_COLORS.low,
    5,
    FIRE_COLORS.medium,
    20,
    FIRE_COLORS.high,
  ];
}

export function pointRadiusExpression(): unknown[] {
  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["get", "frp_mw"], 0],
    0,
    3.2,
    5,
    3.8,
    20,
    4.6,
    100,
    7.2,
  ];
}

export function cellRadiusExpression(): unknown[] {
  return [
    "interpolate",
    ["linear"],
    ["get", "count"],
    1,
    3,
    10,
    4.5,
    100,
    6.5,
    1000,
    9.5,
    5000,
    13,
  ];
}

/**
 * Cells are counts, so they are coloured by density rather than by a single
 * detection's FRP - otherwise one intense detection recolours an entire cell.
 */
export function cellColorExpression(): unknown[] {
  return [
    "step",
    ["get", "count"],
    FIRE_COLORS.low,
    250,
    FIRE_COLORS.medium,
    1500,
    FIRE_COLORS.high,
  ];
}

export function cellsToFeatureCollection(cells: FireCell[]): {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: Record<string, unknown>;
  }>;
} {
  return {
    type: "FeatureCollection",
    features: cells.map((cell) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [cell.longitude, cell.latitude] },
      properties: {
        count: cell.count,
        modis: cell.modis,
        viirs: cell.viirs,
        max_frp_mw: cell.max_frp_mw,
      },
    })),
  };
}

export function emptyFeatures(): FireFeatureCollection {
  return {
    type: "FeatureCollection",
    features: [],
    properties: { returned: 0, total: 0, truncated: false, limit: POINT_LIMIT },
  };
}

/** Counts by sensor for the legend/status line. */
export function sensorTotals(features: FireFeature[]): { modis: number; viirs: number } {
  return features.reduce(
    (totals, feature) => {
      if (feature.properties.sensor === "MODIS") totals.modis += 1;
      if (feature.properties.sensor === "VIIRS") totals.viirs += 1;
      return totals;
    },
    { modis: 0, viirs: 0 },
  );
}

/** Provenance rows for the inspection panel. */
const DAYNIGHT_LABELS: Record<string, string> = { D: "Day", N: "Night" };

export function provenanceRows(observation: Observation): { label: string; value: string }[] {
  const rows: { label: string; value: string }[] = [
    { label: "Coordinates", value: `${observation.latitude.toFixed(4)}, ${observation.longitude.toFixed(4)}` },
    { label: "Acquired (UTC)", value: observation.acquired_at.replace("T", " ").slice(0, 16) + "Z" },
    { label: "Sensor / satellite", value: `${observation.sensor} · ${observation.satellite}` },
    {
      label: "Confidence",
      value:
        observation.confidence_raw !== null
          ? `${observation.confidence_raw} (${observation.confidence_category ?? "n/a"})`
          : (observation.confidence_category ?? "n/a"),
    },
    {
      label: "Brightness",
      value:
        observation.brightness_temperature !== null
          ? `${observation.brightness_temperature.toFixed(1)} K · ${observation.brightness_channel ?? "channel n/a"}`
          : "n/a",
    },
    {
      label: "FRP",
      value: observation.frp_mw !== null ? `${observation.frp_mw.toFixed(2)} MW` : "n/a",
    },
    {
      label: "Scan / track",
      value:
        observation.scan_km !== null && observation.track_km !== null
          ? `${observation.scan_km.toFixed(2)} × ${observation.track_km.toFixed(2)} km`
          : "n/a",
    },
    { label: "Day / night", value: DAYNIGHT_LABELS[(observation.daynight ?? "").toUpperCase()] ?? "n/a" },
    { label: "Product", value: `${observation.source_product}${observation.processing_version ? ` · ${observation.processing_version}` : ""}` },
    { label: "Record id", value: observation.source_record_id },
  ];
  return rows;
}
