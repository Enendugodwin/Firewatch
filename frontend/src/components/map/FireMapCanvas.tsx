import maplibregl from "maplibre-gl";
import type { Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

import type { Bounds, FireCell, FireFeatureCollection } from "@/lib/mapApi";
import {
  cellColorExpression,
  cellRadiusExpression,
  cellsToFeatureCollection,
  frpColorExpression,
  pointRadiusExpression,
} from "./fireLayers";
import { EMPTY_COLLECTION, buildMapStyle } from "./mapStyle";

export interface FireMapHandle {
  flyTo(longitude: number, latitude: number, zoom?: number): void;
}

interface FireMapCanvasProps {
  points: FireFeatureCollection;
  cells: FireCell[];
  heat: boolean;
  basemap: boolean;
  onMoveEnd: (view: { bbox: Bounds; zoom: number }) => void;
  onSelectPoint: (id: string) => void;
  onSelectCell: (cell: FireCell) => void;
  onReady?: (handle: FireMapHandle) => void;
}

export function FireMapCanvas({
  points,
  cells,
  heat,
  basemap,
  onMoveEnd,
  onSelectPoint,
  onSelectCell,
  onReady,
}: FireMapCanvasProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<MapLibreMap | null>(null);
    const loadedRef = useRef(false);
    const handlers = useRef({ onMoveEnd, onSelectPoint, onSelectCell });
    const latest = useRef({ points, cells, heat, basemap });

    useEffect(() => {
      latest.current = { points, cells, heat, basemap };
    }, [points, cells, heat, basemap]);

    // Keep latest callbacks without re-creating the map.
    useEffect(() => {
      handlers.current = { onMoveEnd, onSelectPoint, onSelectCell };
    }, [onMoveEnd, onSelectPoint, onSelectCell]);

    useEffect(() => {
      onReady?.({
        flyTo(longitude: number, latitude: number, zoom = 7) {
          mapRef.current?.flyTo({ center: [longitude, latitude], zoom, duration: 1400 });
        },
      });
      // The handle is stable: it always delegates to the current map instance.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
      if (!containerRef.current || mapRef.current) return;

      const map = new maplibregl.Map({
        container: containerRef.current,
        style: buildMapStyle(),
        center: [8.7, 9.1],
        zoom: 2.4,
        minZoom: 1,
        maxZoom: 15,
        attributionControl: { compact: true },
      });
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

      const report = () => {
        const bounds = map.getBounds();
        handlers.current.onMoveEnd({
          bbox: [
            Math.max(-180, bounds.getWest()),
            Math.max(-85, bounds.getSouth()),
            Math.min(180, bounds.getEast()),
            Math.min(85, bounds.getNorth()),
          ],
          zoom: map.getZoom(),
        });
      };

      map.on("load", () => {
        loadedRef.current = true;

        map.addSource("fires", {
          type: "geojson",
          data: EMPTY_COLLECTION as unknown as GeoJSON.FeatureCollection,
        });
        map.addSource("cells", {
          type: "geojson",
          data: EMPTY_COLLECTION as unknown as GeoJSON.FeatureCollection,
        });

        map.addLayer({
          id: "fire-heat",
          type: "heatmap",
          source: "fires",
          maxzoom: 9,
          paint: {
            "heatmap-weight": [
              "interpolate",
              ["linear"],
              ["coalesce", ["get", "frp_mw"], 0],
              0, 0.05,
              5, 0.35,
              20, 0.7,
              100, 1,
            ],
            "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 1, 1.2, 8, 2.4],
            "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 1, 12, 6, 26, 9, 40],
            "heatmap-opacity": 0.55,
            "heatmap-color": [
              "interpolate",
              ["linear"],
              ["heatmap-density"],
              0, "rgba(0,0,0,0)",
              0.2, "rgba(250,204,21,0.35)",
              0.5, "rgba(251,146,60,0.7)",
              0.8, "rgba(239,68,68,0.9)",
              1, "rgba(255,255,255,0.95)",
            ],
          },
        });

        map.addLayer({
          id: "fire-cells",
          type: "circle",
          source: "cells",
          paint: {
            "circle-radius": cellRadiusExpression() as never,
            "circle-color": cellColorExpression() as never,
            "circle-opacity": 0.4,
            "circle-stroke-color": "rgba(255,255,255,0.5)",
            "circle-stroke-width": 0.5,
            "circle-blur": 0.35,
          },
        });

        map.addLayer({
          id: "fires-points",
          type: "circle",
          source: "fires",
          paint: {
            "circle-radius": pointRadiusExpression() as never,
            "circle-color": frpColorExpression() as never,
            "circle-opacity": 0.9,
            "circle-stroke-width": 1,
            "circle-stroke-color": [
              "match",
              ["get", "sensor"],
              "MODIS", "#72A5F9",
              "VIIRS", "#60D58B",
              "rgba(255,255,255,0.4)",
            ],
          },
        });

        map.addLayer({
          id: "fire-hits",
          type: "circle",
          source: "fires",
          paint: {
            "circle-radius": 11,
            "circle-color": "#ffffff",
            "circle-opacity": 0.01,
          },
        });

        map.on("click", "fire-hits", (event) => {
          const feature = event.features?.[0];
          const id = feature?.properties?.id as string | undefined;
          if (id) handlers.current.onSelectPoint(id);
        });
        map.on("click", "fire-cells", (event) => {
          const feature = event.features?.[0];
          const properties = feature?.properties;
          const geometry = feature?.geometry as GeoJSON.Point | undefined;
          if (!properties || !geometry) return;
          const [longitude, latitude] = geometry.coordinates as [number, number];
          handlers.current.onSelectCell({
            longitude,
            latitude,
            count: Number(properties.count ?? 0),
            modis: Number(properties.modis ?? 0),
            viirs: Number(properties.viirs ?? 0),
            max_frp_mw: properties.max_frp_mw === null ? null : Number(properties.max_frp_mw),
            latest_acquired_at: null,
          });
        });

        (map.getSource("fires") as maplibregl.GeoJSONSource | undefined)?.setData(
          latest.current.points as unknown as GeoJSON.FeatureCollection,
        );
        (map.getSource("cells") as maplibregl.GeoJSONSource | undefined)?.setData(
          cellsToFeatureCollection(latest.current.cells) as unknown as GeoJSON.FeatureCollection,
        );
        map.setLayoutProperty("fire-heat", "visibility", latest.current.heat ? "visible" : "none");
        map.setLayoutProperty("osm", "visibility", latest.current.basemap ? "visible" : "none");

        for (const layer of ["fire-hits", "fire-cells"]) {
          map.on("mouseenter", layer, () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", layer, () => {
            map.getCanvas().style.cursor = "";
          });
        }

        report();
      });

      map.on("moveend", report);

      // Development affordance: lets E2E checks project coordinates and inspect
      // what is actually rendered. Never exposed in a production build.
      if (import.meta.env.DEV) {
        (window as unknown as Record<string, unknown>).__firewatchMap = map;
      }

      return () => {
        map.remove();
        mapRef.current = null;
        loadedRef.current = false;
      };
    }, []);

    // Data + layer state.
    useEffect(() => {
      const map = mapRef.current;
      if (!map || !loadedRef.current) return;
      const source = map.getSource("fires") as maplibregl.GeoJSONSource | undefined;
      source?.setData(points as unknown as GeoJSON.FeatureCollection);
    }, [points]);

    useEffect(() => {
      const map = mapRef.current;
      if (!map || !loadedRef.current) return;
      const source = map.getSource("cells") as maplibregl.GeoJSONSource | undefined;
      source?.setData(cellsToFeatureCollection(cells) as unknown as GeoJSON.FeatureCollection);
    }, [cells]);

    useEffect(() => {
      const map = mapRef.current;
      if (!map || !loadedRef.current) return;
      map.setLayoutProperty("fire-heat", "visibility", heat ? "visible" : "none");
    }, [heat]);

    useEffect(() => {
      const map = mapRef.current;
      if (!map || !loadedRef.current) return;
      map.setLayoutProperty("osm", "visibility", basemap ? "visible" : "none");
    }, [basemap]);

  return (
    <div className="absolute inset-0">
      <div ref={containerRef} className="h-full w-full" aria-label="Global fire map" />
    </div>
  );
}
