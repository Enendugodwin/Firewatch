import { Search, SlidersHorizontal, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { searchPlaces } from "@/lib/mapApi";
import {
  DEFAULT_OBSERVATION_QUERY,
  SATELLITES,
  type ObservationQuery,
  activeFilterCount,
  bboxForPlace,
  filterSummary,
  toLocalInput,
  toUtcIso,
} from "@/lib/query";

const HOUR = 3_600_000;

function isoAt(offsetMs: number): string {
  return new Date(Date.now() + offsetMs).toISOString().replace(/\.\d{3}Z$/, "Z");
}

const PRESETS = [
  { label: "Last 24 h", range: () => ({ startAt: isoAt(-24 * HOUR), endAt: isoAt(0) }) },
  { label: "Last 7 d", range: () => ({ startAt: isoAt(-7 * 24 * HOUR), endAt: isoAt(0) }) },
  { label: "Last 30 d", range: () => ({ startAt: isoAt(-30 * 24 * HOUR), endAt: isoAt(0) }) },
  { label: "Clear", range: () => ({ startAt: undefined, endAt: undefined }) },
];

const label = "text-2xs font-light text-faint";
const control =
  "mt-[5px] w-full rounded-control border border-line/10 bg-canvas/70 px-2 py-[6px] font-mono text-2xs text-ink";

/**
 * Scope builder for stored detections. The period follows the header; this panel
 * narrows the data further (region, sensor, satellite, FRP, confidence,
 * day/night) and is applied explicitly so results never change mid-typing.
 */
export function QueryBuilder({
  query,
  onApply,
  matched,
}: {
  query: ObservationQuery;
  onApply: (next: ObservationQuery) => void;
  matched: number | null;
}) {
  const [draft, setDraft] = useState<ObservationQuery>(query);
  const [term, setTerm] = useState("");
  const [results, setResults] = useState<
    Array<{ name: string; kind: string; latitude: number; longitude: number; zoom: number }>
  >([]);
  const [searching, setSearching] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setDraft(query);
  }, [query]);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    const trimmed = term.trim();
    if (trimmed.length < 2) {
      setResults([]);
      return;
    }
    setSearching(true);
    timer.current = setTimeout(async () => {
      try {
        const response = await searchPlaces(trimmed);
        setResults(response.results);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [term]);

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(query), [draft, query]);
  const active = activeFilterCount(query);

  function patch(next: Partial<ObservationQuery>) {
    setDraft((current) => ({ ...current, ...next }));
  }

  return (
    <section className="shell shadow-glass">
      <div className="shell-inner">
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line/[0.07] px-[22px] pb-[14px] pt-[18px]">
          <div className="min-w-0">
            <h2 className="inline-flex items-center gap-2 text-[13px] font-medium tracking-[0.01em] text-ink">
              <SlidersHorizontal className="size-3.5 text-faint" aria-hidden />
              Query
              {active > 0 ? (
                <span className="rounded-full border border-line/12 px-[6px] py-[1px] font-mono text-3xs text-muted">
                  {active} active
                </span>
              ) : null}
            </h2>
            <p className="mt-[3px] text-2xs font-light leading-relaxed text-muted">
              {filterSummary(query)}
              {matched !== null ? (
                <>
                  {" "}
                  · <span className="text-ink">{matched.toLocaleString("en-US")}</span> detections
                  match
                </>
              ) : null}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setTerm("");
                setResults([]);
                setDraft(DEFAULT_OBSERVATION_QUERY);
                onApply(DEFAULT_OBSERVATION_QUERY);
              }}
              className="btn-glass px-3 py-[5px] text-3xs"
            >
              Reset
            </button>
            <button
              type="button"
              onClick={() => onApply(draft)}
              disabled={!dirty}
              className="btn-primary px-3 py-[5px] text-3xs disabled:opacity-40"
            >
              Apply query
            </button>
          </div>
        </header>

        <div className="grid gap-3 px-[22px] py-[16px] sm:grid-cols-2 xl:grid-cols-4">
          <div className="sm:col-span-2 xl:col-span-4">
            <div className="flex flex-wrap items-end gap-3">
              <label className="block">
                <span className={label}>From (UTC)</span>
                <input
                  aria-label="From (UTC)"
                  type="datetime-local"
                  value={toLocalInput(draft.startAt)}
                  onChange={(event) => patch({ startAt: toUtcIso(event.target.value) })}
                  className={`${control} w-[13.5rem]`}
                />
              </label>
              <label className="block">
                <span className={label}>To (UTC)</span>
                <input
                  aria-label="To (UTC)"
                  type="datetime-local"
                  value={toLocalInput(draft.endAt)}
                  onChange={(event) => patch({ endAt: toUtcIso(event.target.value) })}
                  className={`${control} w-[13.5rem]`}
                />
              </label>
              <div className="flex flex-wrap items-center gap-1 pb-[6px]">
                <span className="mr-1 text-3xs uppercase tracking-[0.1em] text-faint">Presets</span>
                {PRESETS.map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => patch(preset.range())}
                    className="rounded-full border border-line/12 px-2 py-[3px] text-3xs text-muted transition-colors duration-150 hover:border-line/25 hover:text-ink"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>
            <p className="mt-[6px] text-3xs font-light text-faint">
              Times are UTC. A window overrides the header period; leave both empty to use it.
            </p>
          </div>

          <div className="sm:col-span-2">
            <span className={label}>Region (optional)</span>
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-2 top-[13px] size-3 text-faint"
                aria-hidden
              />
              <input
                value={term}
                onChange={(event) => setTerm(event.target.value)}
                placeholder="Country, city or lat,lon"
                aria-label="Search a region to constrain the query"
                className={`${control} pl-7`}
              />
              {draft.region ? (
                <button
                  type="button"
                  onClick={() => patch({ region: null, bbox: undefined })}
                  className="absolute right-1.5 top-[9px] inline-flex items-center gap-1 rounded-full border border-line/15 px-2 py-[2px] text-3xs text-muted hover:text-ink"
                >
                  {draft.region}
                  <X className="size-2.5" aria-hidden />
                </button>
              ) : null}
              {term.trim().length >= 2 && results.length > 0 ? (
                <ul className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-control border border-line/15 bg-panel shadow-lift">
                  {results.slice(0, 5).map((place) => (
                    <li key={`${place.kind}-${place.name}`}>
                      <button
                        type="button"
                        onClick={() => {
                          patch({
                            region: place.name,
                            bbox: bboxForPlace(place.latitude, place.longitude, place.zoom),
                          });
                          setTerm("");
                          setResults([]);
                        }}
                        className="flex w-full items-center justify-between gap-2 px-2 py-[6px] text-left text-3xs text-muted hover:bg-line/[0.05] hover:text-ink"
                      >
                        <span>{place.name}</span>
                        <span className="font-mono text-faint">
                          {place.latitude.toFixed(2)}, {place.longitude.toFixed(2)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
              {searching ? (
                <span className="absolute right-2 top-[13px] text-3xs text-faint">…</span>
              ) : null}
            </div>
          </div>

          <label className="block">
            <span className={label}>Sensor</span>
            <select
              aria-label="Sensor"
              value={draft.sensor ?? ""}
              onChange={(event) =>
                patch({ sensor: (event.target.value || undefined) as ObservationQuery["sensor"] })
              }
              className={control}
            >
              <option value="">MODIS + VIIRS</option>
              <option value="MODIS">MODIS only</option>
              <option value="VIIRS">VIIRS only</option>
            </select>
          </label>

          <label className="block">
            <span className={label}>Satellite</span>
            <select
              aria-label="Satellite"
              value={draft.satellite ?? ""}
              onChange={(event) => patch({ satellite: event.target.value || undefined })}
              className={control}
            >
              <option value="">Any satellite</option>
              {SATELLITES.map((satellite) => (
                <option key={satellite} value={satellite}>
                  {satellite}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className={label}>Minimum FRP (MW)</span>
            <input
              aria-label="Minimum FRP"
              type="number"
              min={0}
              step={1}
              value={draft.minFrp ?? 0}
              onChange={(event) => {
                const value = Number(event.target.value);
                patch({ minFrp: Number.isFinite(value) && value > 0 ? value : undefined });
              }}
              className={control}
            />
          </label>

          <label className="block">
            <span className={label}>Confidence</span>
            <select
              aria-label="Confidence"
              value={draft.minConfidence ?? "low"}
              onChange={(event) =>
                patch({
                  minConfidence:
                    event.target.value === "low"
                      ? undefined
                      : (event.target.value as ObservationQuery["minConfidence"]),
                })
              }
              className={control}
            >
              <option value="low">Any confidence</option>
              <option value="nominal">Nominal or higher</option>
              <option value="high">High only</option>
            </select>
          </label>

          <label className="block">
            <span className={label}>Day / night</span>
            <select
              aria-label="Day / night"
              value={draft.daynight ?? ""}
              onChange={(event) =>
                patch({
                  daynight: (event.target.value || undefined) as ObservationQuery["daynight"],
                })
              }
              className={control}
            >
              <option value="">Day and night</option>
              <option value="D">Daytime only</option>
              <option value="N">Night-time only</option>
            </select>
          </label>

          <label className="flex items-center gap-2 self-end py-[6px] text-2xs font-light text-muted">
            <input
              aria-label="Include synthetic fixture"
              type="checkbox"
              checked={Boolean(draft.synthetic)}
              onChange={(event) => patch({ synthetic: event.target.checked })}
              className="size-3.5 rounded border-line/40 bg-transparent accent-[#60D58B]"
            />
            Include synthetic fixture
          </label>
        </div>
      </div>
    </section>
  );
}
