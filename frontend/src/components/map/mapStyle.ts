import type { LayerSpecification, StyleSpecification } from "maplibre-gl";

/**
 * Self-contained dark style: just the orbital field. The OSM basemap is added
 * separately (see BASEMAP_LAYER) so that a slow or blocked tile server can never
 * stop the data layers from loading. No API key, no external style dependency.
 */
export const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export const BASEMAP_SOURCE = "osm";
export const BASEMAP_LAYER = "osm";

export function buildMapStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": "#05070F" },
      },
    ],
  };
}

/** Muted, desaturated context tiles that sit under the fire data. */
export function buildBasemapSource() {
  return {
    type: "raster" as const,
    tiles: [OSM_TILES],
    tileSize: 256,
    maxzoom: 19,
    attribution: "\u00a9 OpenStreetMap contributors",
  };
}

export const BASEMAP_LAYER_SPEC: LayerSpecification = {
  id: BASEMAP_LAYER,
  type: "raster",
  source: BASEMAP_SOURCE,
  paint: {
    "raster-opacity": 0.45,
    "raster-saturation": -1,
    "raster-contrast": 0.05,
    "raster-brightness-max": 0.16,
    "raster-brightness-min": 0.02,
  },
};

export const EMPTY_COLLECTION = {
  type: "FeatureCollection" as const,
  features: [],
};
