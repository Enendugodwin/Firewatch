import type { StyleSpecification } from "maplibre-gl";

/**
 * Self-contained dark style: the orbital canvas plus an optional, heavily
 * muted OSM raster basemap for geographic context. No API key, no external
 * style dependency â€” if tiles fail to load the data layers still work.
 */
export const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export function buildMapStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: [OSM_TILES],
        tileSize: 256,
        maxzoom: 19,
        attribution: "Â© OpenStreetMap contributors",
      },
    },
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": "#05070F" },
      },
      {
        id: "osm",
        type: "raster",
        source: "osm",
        paint: {
          "raster-opacity": 0.55,
          "raster-saturation": -1,
          "raster-contrast": 0.18,
          "raster-brightness-max": 0.24,
          "raster-brightness-min": 0.02,
        },
      },
    ],
  };
}

export const EMPTY_COLLECTION = {
  type: "FeatureCollection" as const,
  features: [],
};
