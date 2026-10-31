import type { FireFeature, FireFeatureCollection, FireCell } from "@/lib/mapApi";

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

/** Any palette with three severity stops (map themes provide their own). */
export interface FireColors {
  low: string;
  medium: string;
  high: string;
}

export const SENSOR_COLORS = {
  MODIS: "#72A5F9",
  VIIRS: "#60D58B",
} as const;

export function useAggregate(zoom: number): boolean {
  return zoom < AGGREGATE_ZOOM;
}

export function frpColorExpression(colors: FireColors = FIRE_COLORS): unknown[] {
  return [
    "step",
    ["coalesce", ["get", "frp_mw"], 0],
    colors.low,
    5,
    colors.medium,
    20,
    colors.high,
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
export function cellColorExpression(colors: FireColors = FIRE_COLORS): unknown[] {
  return ["step", ["get", "count"], colors.low, 250, colors.medium, 1500, colors.high];
}

/** Heatmap ramp for a theme; alpha stops keep the basemap visible. */
export function heatColorExpression(theme: {
  low: string;
  mid: string;
  high: string;
  top: string;
}): unknown[] {
  return [
    "interpolate",
    ["linear"],
    ["heatmap-density"],
    0,
    "rgba(0,0,0,0)",
    0.2,
    theme.low,
    0.55,
    theme.mid,
    0.85,
    theme.high,
    1,
    theme.top,
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

// Provenance rows live in lib/provenance so the calendar can reuse them.
export { provenanceRows } from "@/lib/provenance";
