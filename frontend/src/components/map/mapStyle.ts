import type { LayerSpecification, StyleSpecification } from "maplibre-gl";

/**
 * Self-contained styles. The fire layers live in their own zero-dependency base
 * style; the OSM raster basemap is attached afterwards so a slow, rate-limited
 * or blocked tile server can never stop the data from loading.
 */

export const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export const BASEMAP_SOURCE = "osm";
export const BASEMAP_LAYER = "osm";

export type MapThemeId = "daylight" | "terrain" | "orbital" | "paper";

export interface MapTheme {
  id: MapThemeId;
  /** Label shown in the layer panel. */
  label: string;
  /** One-line description used as the option hint. */
  hint: string;
  /** Fallback fill when the basemap is off or its tiles fail. */
  background: string;
  basemap: {
    opacity: number;
    saturation: number;
    contrast: number;
    brightnessMin: number;
    brightnessMax: number;
    hueRotate: number;
  };
  /** Detection colours, stepped by FRP (points) and by density (cells). */
  fire: { low: string; medium: string; high: string };
  /** Sensor outline colours, tuned for the theme's contrast. */
  sensor: { MODIS: string; VIIRS: string };
  stroke: string;
  strokeWidth: number;
  cellOpacity: number;
  heat: {
    low: string;
    mid: string;
    high: string;
    top: string;
    opacity: number;
    intensity: number;
  };
  /** Two stops used to preview the theme in the picker. */
  swatch: [string, string];
}

/**
 * Bright earth is the default: the fire signal reads best over a legible
 * basemap, and dark-only maps are hard to use on projectors and in daylight.
 * The orbital dark theme stays available for night work.
 */
export const MAP_THEMES: Record<MapThemeId, MapTheme> = {
  daylight: {
    id: "daylight",
    label: "Daylight",
    hint: "Bright earth, deep detection colours",
    background: "#A9C3D4",
    basemap: {
      opacity: 1,
      saturation: 0.35,
      contrast: 0.02,
      brightnessMin: 0,
      brightnessMax: 1,
      hueRotate: 0,
    },
    fire: { low: "#B45309", medium: "#EA580C", high: "#B91C1C" },
    sensor: { MODIS: "#1D4ED8", VIIRS: "#A21CAF" },
    stroke: "rgba(255,255,255,0.95)",
    strokeWidth: 1.6,
    cellOpacity: 0.55,
    heat: {
      low: "rgba(250,204,21,0.35)",
      mid: "rgba(234,88,12,0.6)",
      high: "rgba(153,27,27,0.8)",
      top: "rgba(120,20,20,0.9)",
      opacity: 0.55,
      intensity: 1.6,
    },
    swatch: ["#DCE8F0", "#7FA3BC"],
  },
  terrain: {
    id: "terrain",
    label: "Terrain",
    hint: "Warm, sepia-toned land",
    background: "#D8CFB8",
    basemap: {
      opacity: 1,
      saturation: 0.25,
      contrast: 0.02,
      brightnessMin: 0,
      brightnessMax: 1,
      hueRotate: 20,
    },
    fire: { low: "#92400E", medium: "#C2410C", high: "#7F1D1D" },
    sensor: { MODIS: "#1E3A8A", VIIRS: "#A21CAF" },
    stroke: "rgba(255,255,255,0.96)",
    strokeWidth: 1.7,
    cellOpacity: 0.6,
    heat: {
      low: "rgba(253,224,71,0.4)",
      mid: "rgba(194,65,12,0.65)",
      high: "rgba(127,29,29,0.85)",
      top: "rgba(90,20,20,0.92)",
      opacity: 0.6,
      intensity: 1.7,
    },
    swatch: ["#E3EBD8", "#8FA877"],
  },
  orbital: {
    id: "orbital",
    label: "Orbital",
    hint: "Dark field for night work",
    background: "#05070F",
    basemap: {
      opacity: 0.45,
      saturation: -1,
      contrast: 0.05,
      brightnessMin: 0.02,
      brightnessMax: 0.16,
      hueRotate: 0,
    },
    fire: { low: "#FACC15", medium: "#FB923C", high: "#EF4444" },
    sensor: { MODIS: "#72A5F9", VIIRS: "#E879F9" },
    stroke: "rgba(255,255,255,0.5)",
    strokeWidth: 1,
    cellOpacity: 0.4,
    heat: {
      low: "rgba(250,204,21,0.35)",
      mid: "rgba(251,146,60,0.7)",
      high: "rgba(239,68,68,0.9)",
      top: "rgba(255,255,255,0.95)",
      opacity: 0.55,
      intensity: 2.4,
    },
    swatch: ["#0B1020", "#1E2A3D"],
  },
  paper: {
    id: "paper",
    label: "Paper",
    hint: "Near-white, for screenshots and print",
    background: "#F2F0EA",
    basemap: {
      opacity: 1,
      saturation: -0.85,
      contrast: 0,
      brightnessMin: 0,
      brightnessMax: 1,
      hueRotate: 0,
    },
    fire: { low: "#A16207", medium: "#C2410C", high: "#991B1B" },
    sensor: { MODIS: "#1E40AF", VIIRS: "#A21CAF" },
    stroke: "rgba(17,24,39,0.6)",
    strokeWidth: 1.1,
    cellOpacity: 0.6,
    heat: {
      low: "rgba(202,138,4,0.3)",
      mid: "rgba(194,65,12,0.55)",
      high: "rgba(153,27,27,0.75)",
      top: "rgba(120,20,20,0.85)",
      opacity: 0.5,
      intensity: 1.5,
    },
    swatch: ["#FBFAF6", "#C9C4B6"],
  },
};

export const DEFAULT_THEME: MapThemeId = "daylight";

export const THEME_ORDER: MapThemeId[] = ["daylight", "terrain", "orbital", "paper"];

export function buildMapStyle(theme: MapTheme = MAP_THEMES[DEFAULT_THEME]): StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": theme.background },
      },
    ],
  };
}

export function buildBasemapSource() {
  return {
    type: "raster" as const,
    tiles: [OSM_TILES],
    tileSize: 256,
    maxzoom: 19,
    attribution: "\u00a9 OpenStreetMap contributors",
  };
}

/** Muted raster context tiles; the paint is re-applied whenever the theme changes. */
export function buildBasemapLayer(theme: MapTheme): LayerSpecification {
  return {
    id: BASEMAP_LAYER,
    type: "raster",
    source: BASEMAP_SOURCE,
    paint: {
      "raster-opacity": theme.basemap.opacity,
      "raster-saturation": theme.basemap.saturation,
      "raster-contrast": theme.basemap.contrast,
      "raster-brightness-min": theme.basemap.brightnessMin,
      "raster-brightness-max": theme.basemap.brightnessMax,
      "raster-hue-rotate": theme.basemap.hueRotate,
    },
  };
}

export const EMPTY_COLLECTION = {
  type: "FeatureCollection" as const,
  features: [],
};
