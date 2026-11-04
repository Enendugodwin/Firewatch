import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Layers, Loader2, Search, SlidersHorizontal, X } from "lucide-react";

import { PageHeader } from "@/components/ui/ModuleStatus";
import { Badge } from "@/components/ui/Badge";
import { HotspotPanel } from "@/components/map/HotspotPanel";
import {
  DEFAULT_FILTERS,
  MapFilters,
  type MapFiltersState,
} from "@/components/map/MapFilters";
import { AGGREGATE_ZOOM, POINT_LIMIT, emptyFeatures, useAggregate } from "@/components/map/fireLayers";
import { MAP_THEMES } from "@/components/map/mapStyle";
import { findNavItemByKey } from "@/config/nav";
import { useModules, useSystemStatus } from "@/lib/queries";
import {
  fetchAggregate,
  fetchFireFeatures,
  fetchObservation,
  searchPlaces,
  type Bounds,
  type FireCell,
  type FireFeatureCollection,
  type FireQuery,
  type GeoPlace,
} from "@/lib/mapApi";
import { formatCount } from "@/lib/format";
import { useUiStore } from "@/store/ui";

const FireMapCanvas = lazy(() =>
  import("@/components/map/FireMapCanvas").then((module) => ({ default: module.FireMapCanvas })),
);

const WORLD: Bounds = [-180, -85, 180, 85];

interface ViewState {
  bbox: Bounds;
  zoom: number;
}

interface Meta {
  aggregated: boolean;
  shown: number;
  total: number;
  cellDegrees: number | null;
  truncated: boolean;
  limit: number;
}

const EMPTY_META: Meta = {
  aggregated: true,
  shown: 0,
  total: 0,
  cellDegrees: null,
  truncated: false,
  limit: POINT_LIMIT,
};

export function FireMapPage() {
  const navItem = findNavItemByKey("fire-map");
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "fire-map");
  const { data: status } = useSystemStatus();
  const dateRange = useUiStore((state) => state.dateRange);

  const [filters, setFilters] = useState<MapFiltersState>(DEFAULT_FILTERS);
  const [view, setView] = useState<ViewState>({ bbox: WORLD, zoom: 2 });
  const [points, setPoints] = useState<FireFeatureCollection>(emptyFeatures());
  const [cells, setCells] = useState<FireCell[]>([]);
  const [meta, setMeta] = useState<Meta>(EMPTY_META);
  const [loading, setLoading] = useState(true);
  const [mapReady, setMapReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<GeoPlace[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);

  const mapRef = useRef<{ flyTo: (lon: number, lat: number, zoom?: number) => void } | null>(null);

  const hasSynthetic = (status?.data.synthetic_observations ?? 0) > 0;
  const sensor = useMemo(() => {
    if (filters.modis && filters.viirs) return undefined;
    if (filters.modis) return "MODIS" as const;
    if (filters.viirs) return "VIIRS" as const;
    return null;
  }, [filters.modis, filters.viirs]);

  const query: FireQuery | null = useMemo(() => {
    if (sensor === null) return null;
    return {
      bbox: view.bbox,
      sensor,
      minFrp: filters.minFrp || undefined,
      daynight: filters.daynight === "all" ? undefined : filters.daynight,
      minConfidence: filters.minConfidence,
      synthetic: filters.includeSynthetic ? undefined : false,
    harmonized: filters.harmonized,
      startDate: dateRange.start,
      endDate: dateRange.end,
    };
  }, [view.bbox, sensor, filters, dateRange.start, dateRange.end]);

  // Viewport fetch: aggregated when zoomed out, individual points when close.
  useEffect(() => {
    if (!query) {
      setPoints(emptyFeatures());
      setCells([]);
      setMeta(EMPTY_META);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      const aggregated = useAggregate(view.zoom);

      const request = aggregated
        ? fetchAggregate(query, view.zoom, controller.signal).then((payload) => {
            setCells(payload.cells);
            setPoints(emptyFeatures());
            setMeta({
              aggregated: true,
              shown: payload.returned_cells,
              total: payload.total_detections,
              cellDegrees: payload.cell_degrees,
              truncated: payload.truncated,
              limit: 0,
            });
          })
        : fetchFireFeatures(query, POINT_LIMIT, controller.signal).then((payload) => {
            setPoints(payload);
            setCells([]);
            setMeta({
              aggregated: false,
              shown: payload.features.length,
              total: payload.properties.total,
              cellDegrees: null,
              truncated: payload.properties.truncated,
              limit: payload.properties.limit,
            });
          });

      request
        .catch((cause: unknown) => {
          if (controller.signal.aborted) return;
          setError(cause instanceof Error ? cause.message : "Map request failed.");
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 260);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, view.zoom]);

  const detail = useQuery({
    queryKey: ["observation", selectedId],
    queryFn: () => fetchObservation(selectedId as string),
    enabled: Boolean(selectedId),
    staleTime: 60_000,
    retry: 1,
  });

  useEffect(() => {
    setSearchResults([]);
    setSearchOpen(false);
  }, [searchTerm]);

  async function runSearch(event: React.FormEvent) {
    event.preventDefault();
    const term = searchTerm.trim();
    if (!term) return;
    try {
      const response = await searchPlaces(term);
      setSearchResults(response.results);
      const first = response.results[0];
      if (first) {
        // Enter jumps straight to the best match; the list stays available for
        // alternative matches.
        mapRef.current?.flyTo(first.longitude, first.latitude, first.zoom);
        setSearchOpen(false);
      } else {
        setSearchOpen(true);
      }
    } catch {
      setSearchResults([]);
      setSearchOpen(true);
    }
  }

  function goTo(place: GeoPlace) {
    mapRef.current?.flyTo(place.longitude, place.latitude, place.zoom);
    setSearchOpen(false);
  }

  const statusLine = query
    ? meta.aggregated
      ? `${filters.harmonized ? "Harmonized · " : ""}${formatCount(meta.shown)} cells · ${formatCount(meta.total)} detections${meta.cellDegrees ? ` · ${meta.cellDegrees.toFixed(2)}° grid` : ""}`
      : `${filters.harmonized ? "Harmonized · " : ""}${formatCount(meta.shown)} of ${formatCount(meta.total)} detections${meta.truncated ? " (truncated)" : ""}`
    : "No sensor selected";

  return (
    <div>
      <div className="relative z-20">
      <PageHeader
        eyebrow="Firewatch X / Monitoring"
        title={module?.label ?? navItem?.label ?? "Global Fire Map"}
        description="Satellite detections from stored observations. Zoomed-out views are served as gridded counts; individual points appear as you zoom in."
        status={module?.status ?? "in_progress"}
        phase={module?.phase ?? "Phase 4"}
        actions={
          <form onSubmit={runSearch} className="relative">
            <div className="flex items-center gap-2 rounded-full border border-line/10 bg-line/[0.03] px-3 py-1.5">
              <Search className="size-3.5 text-faint" aria-hidden />
              <input
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Country, city or lat,lon"
                aria-label="Search the map"
                className="w-40 bg-transparent text-xs font-light text-ink placeholder:text-faint focus:outline-none sm:w-48"
              />
              {searchTerm ? (
                <button
                  type="button"
                  onClick={() => setSearchTerm("")}
                  aria-label="Clear search"
                  className="text-faint hover:text-ink"
                >
                  <X className="size-3" aria-hidden />
                </button>
              ) : null}
            </div>

            {searchOpen ? (
              <div className="absolute right-0 top-[calc(100%+8px)] z-30 w-64 overflow-hidden rounded-card border border-line/[0.1] bg-panel shadow-lift">
                {searchResults.length === 0 ? (
                  <p className="px-3 py-4 text-center text-2xs font-light text-faint">
                    No match. Try “Nigeria”, “Lagos” or “8.5, 9.1”.
                  </p>
                ) : (
                  <ul>
                    {searchResults.map((place) => (
                      <li key={`${place.kind}-${place.name}`}>
                        <button
                          type="button"
                          onClick={() => goTo(place)}
                          className="flex w-full items-center justify-between gap-3 px-3 py-[7px] text-left text-xs font-light text-muted transition-colors duration-150 hover:bg-line/[0.05] hover:text-ink"
                        >
                          <span>{place.name}</span>
                          <span className="text-3xs uppercase tracking-[0.1em] text-faint">
                            {place.kind}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : null}
          </form>
        }
      />
      </div>

      <div
        className="relative h-[calc(100dvh-21rem)] min-h-[420px] overflow-hidden rounded-card border border-line/[0.1] sm:h-[calc(100dvh-17rem)] sm:min-h-[520px]"
        aria-busy={loading || !mapReady}
      >
        <Suspense
          fallback={
            <div className="absolute inset-0 flex items-center justify-center bg-canvas">
              <span className="inline-flex items-center gap-2 text-xs font-light text-faint">
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Loading map renderer…
              </span>
            </div>
          }
        >
          <FireMapCanvas
            onReady={(handle) => {
              mapRef.current = handle;
              setMapReady(true);
            }}
            points={points}
            cells={cells}
            heat={filters.heat}
            basemap={filters.basemap}
            theme={filters.theme}
            onMoveEnd={setView}
            onSelectPoint={setSelectedId}
            onSelectCell={(cell) =>
              mapRef.current?.flyTo(cell.longitude, cell.latitude, Math.max(AGGREGATE_ZOOM, view.zoom + 1.8))
            }
          />
        </Suspense>

        {!mapReady ? (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 z-[5] animate-pulse bg-[linear-gradient(120deg,rgba(148,163,184,0.06),rgba(239,68,68,0.05),rgba(148,163,184,0.06))] motion-reduce:animate-none"
          />
        ) : null}

        {loading || !mapReady ? (
          <div className="pointer-events-none absolute left-1/2 top-3 z-30 -translate-x-1/2">
            <div
              role="status"
              aria-live="polite"
              className="flex items-center gap-2 rounded-full border border-line/15 bg-panel/95 px-4 py-2 text-2xs font-light text-muted shadow-glass backdrop-blur-glass"
            >
              <Loader2 className="size-3.5 animate-spin text-accent motion-reduce:animate-none" aria-hidden />
              <span>
                {!mapReady
                  ? "Initialising map renderer…"
                  : meta.aggregated || view.zoom < AGGREGATE_ZOOM
                    ? "Loading aggregated hotspots…"
                    : "Loading hotspot detections…"}
              </span>
            </div>
          </div>
        ) : null}

        <div className="pointer-events-none absolute inset-0 z-10 p-3 pb-4">
          <div className="flex h-full flex-col justify-between gap-3">
            <div className="flex items-start justify-between gap-3">
              <div className="pointer-events-auto hidden sm:block">
                <MapFilters
                  filters={filters}
                  onChange={setFilters}
                  hasSynthetic={hasSynthetic}
                  onReset={() => setFilters(DEFAULT_FILTERS)}
                />
              </div>

              <div className="pointer-events-auto flex items-start justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setFilters({ ...filters, harmonized: !filters.harmonized })}
                  aria-pressed={filters.harmonized}
                  title="Show the harmonized view: VIIRS detections already associated with MODIS are removed"
                  className={
                    filters.harmonized
                      ? "inline-flex items-center gap-1.5 rounded-full border border-accent/40 bg-accent/10 px-3 py-1.5 text-2xs text-accent"
                      : "inline-flex items-center gap-1.5 rounded-full border border-line/10 bg-panel/90 px-3 py-1.5 text-2xs text-muted"
                  }
                >
                  <Layers className="size-3" aria-hidden />
                  Harmonized
                </button>
                <button
                  type="button"
                  onClick={() => setMobileFiltersOpen((open) => !open)}
                  aria-label="Toggle filters"
                  className="inline-flex size-8 items-center justify-center rounded-full border border-line/10 bg-panel/90 text-muted sm:hidden"
                >
                  <SlidersHorizontal className="size-3.5" aria-hidden />
                </button>
                <HotspotPanel
                  observation={detail.data ?? null}
                  loading={detail.isLoading}
                  error={detail.isError ? "Could not load this detection." : null}
                  onClose={() => setSelectedId(null)}
                />
              </div>
            </div>

            <div className="flex flex-wrap items-end gap-2 pb-6 pr-14 sm:pb-0">
              <div className="pointer-events-auto flex max-w-full flex-wrap items-center gap-2 rounded-full border border-line/[0.1] bg-panel/90 px-3 py-1.5 text-3xs font-light text-muted backdrop-blur-glass">
                {loading ? <Loader2 className="size-3 animate-spin text-faint" aria-hidden /> : null}
                <span>{statusLine}</span>
                <span className="hidden text-line/20 sm:inline">|</span>
                <span className="hidden font-mono sm:inline">
                  {dateRange.start} → {dateRange.end}
                </span>
                {meta.aggregated ? <Badge tone="neutral">aggregated</Badge> : null}
              </div>
              <div className="pointer-events-auto flex max-w-full flex-wrap items-center gap-x-3 gap-y-1 rounded-full border border-line/[0.1] bg-panel/90 px-3 py-1.5 text-3xs font-light text-faint backdrop-blur-glass">
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className="size-1.5 rounded-full"
                    style={{ backgroundColor: MAP_THEMES[filters.theme].sensor.MODIS }}
                  />{" "}
                  MODIS outline
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className="size-1.5 rounded-full"
                    style={{ backgroundColor: MAP_THEMES[filters.theme].sensor.VIIRS }}
                  />{" "}
                  VIIRS outline
                </span>
                <span
                  className="inline-flex items-center gap-1"
                  role="group"
                  aria-label={
                    meta.aggregated
                      ? "Density ramp: under 250, 250 to 1499, 1500 or more detections per cell"
                      : "FRP ramp: under 5, 5 to 19, 20 or more megawatts"
                  }
                  title={
                    meta.aggregated
                      ? "Cell colour and size: 1–249 / 250–1499 / 1500+ detections"
                      : "Point colour and size: <5 / 5–19 / 20+ MW"
                  }
                >
                  {[MAP_THEMES[filters.theme].fire.low, MAP_THEMES[filters.theme].fire.medium, MAP_THEMES[filters.theme].fire.high].map(
                    (colour) => (
                      <span
                        key={colour}
                        className="size-1.5 rounded-full"
                        style={{ backgroundColor: colour }}
                        aria-hidden
                      />
                    ),
                  )}
                  <span className="hidden sm:inline">
                    {meta.aggregated ? "density (detections/cell)" : "FRP (MW)"}
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>

        {mobileFiltersOpen ? (
          <div className="absolute left-3 top-3 z-20 sm:hidden">
            <MapFilters
              filters={filters}
              onChange={setFilters}
              hasSynthetic={hasSynthetic}
              onReset={() => setFilters(DEFAULT_FILTERS)}
            />
          </div>
        ) : null}

        {error ? (
          <div className="absolute inset-x-3 bottom-14 z-20 flex items-start gap-2 rounded-card border border-danger/30 bg-panel/95 px-3 py-2 text-2xs font-light text-danger">
            <AlertTriangle className="mt-[1px] size-3 shrink-0" aria-hidden />
            {error}
          </div>
        ) : null}

        {!loading && !error && meta.total === 0 ? (
          <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center">
            <div className="pointer-events-auto rounded-card border border-line/[0.1] bg-panel/95 px-4 py-3 text-center">
              <p className="text-xs text-ink">No detections in this view</p>
              <p className="mt-1 text-2xs font-light text-faint">
                Widen the period, clear a filter, or check the sensor toggles.
              </p>
            </div>
          </div>
        ) : null}
      </div>

      <p className="mt-2 text-2xs font-light leading-relaxed text-faint">
        Detections are thermal anomalies, not fires. Below zoom {AGGREGATE_ZOOM} the map shows
        gridded counts; each dot is then a number of detections, not a single fire. Basemap tiles
        © OpenStreetMap contributors; detections © NASA FIRMS.
      </p>
    </div>
  );
}
