import { useQuery } from "@tanstack/react-query";
import { Download, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { ObservationDialog } from "@/components/calendar/ObservationDialog";
import { QueryBuilder } from "@/components/query/QueryBuilder";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel, StatTile } from "@/components/ui/Panel";
import { apiFetch } from "@/lib/api";
import type { CalendarResponse } from "@/lib/calendarApi";
import { formatCount, formatFrp } from "@/lib/format";
import {
  DEFAULT_OBSERVATION_QUERY,
  detectionExportUrl,
  observationParams,
  type ObservationQuery,
} from "@/lib/query";
import { useUiStore } from "@/store/ui";
import type { Observation, ObservationPage } from "@/types/api";

/**
 * Query workspace: narrow the stored detections by scope and read the matching
 * rows directly. Numbers come from the calendar aggregate for the same scope, so
 * the table and the totals can never disagree about what matched.
 */
export function QueryPage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const [query, setQuery] = useState<ObservationQuery>(DEFAULT_OBSERVATION_QUERY);
  const [selected, setSelected] = useState<Observation | null>(null);

  // A time window overrides the header period; otherwise the header applies.
  const windowStart = query.startAt ? query.startAt.slice(0, 10) : dateRange.start;
  const windowEnd = query.endAt ? query.endAt.slice(0, 10) : dateRange.end;

  const params = useMemo(() => observationParams(query), [query]);

  const summaryParams = useMemo(
    () =>
      observationParams(query, {
        start_date: windowStart,
        end_date: windowEnd,
        granularity: "day",
      }),
    [query, windowStart, windowEnd],
  );

  const observations = useQuery({
    queryKey: ["query", "observations", params.toString()],
    queryFn: ({ signal }) =>
      apiFetch<ObservationPage>(`/api/v1/fires?${params.toString()}&limit=200`, { signal }),
    staleTime: 30_000,
    retry: 1,
  });

  const summary = useQuery({
    queryKey: ["query", "summary", summaryParams.toString()],
    queryFn: ({ signal }) =>
      apiFetch<CalendarResponse>(`/api/v1/calendar?${summaryParams.toString()}`, { signal }),
    staleTime: 30_000,
    retry: 1,
  });

  const totals = summary.data?.totals;
  const rows = observations.data?.items ?? [];
  const matched = observations.data?.total ?? null;

  // Export the whole match set, not the 200 rows on screen.
  const exportParams = useMemo(() => {
    const next = new URLSearchParams(params);
    next.set("limit", String(Math.min(matched ?? 100_000, 500_000)));
    return next;
  }, [params, matched]);

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / Intelligence"
        title="Data Query"
        phase="Phase 5"
        description="Filter the stored detections and read the matching rows. The period follows the header; every row is a detection, not a fire, and carries its full NASA FIRMS provenance."
      />

      <div className="mb-4">
        <QueryBuilder query={query} onApply={setQuery} matched={matched} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Detections matched"
          value={formatCount(totals?.detections ?? 0)}
          hint={
            query.startAt && query.endAt
              ? `${query.startAt.slice(0, 16).replace("T", " ")}Z → ${query.endAt
                  .slice(0, 16)
                  .replace("T", " ")}Z`
              : `${dateRange.start} → ${dateRange.end} (UTC)`
          }
        />
        <StatTile
          label="MODIS / VIIRS"
          value={`${formatCount(totals?.modis ?? 0)} / ${formatCount(totals?.viirs ?? 0)}`}
          hint="Sensor split for the matched rows"
        />
        <StatTile
          label="FRP sum"
          value={formatFrp(totals?.frp_sum_mw ?? 0)}
          hint={`Peak ${formatFrp(totals?.frp_max_mw ?? null)}`}
        />
        <StatTile
          label="High confidence"
          value={formatCount(totals?.high_confidence ?? 0)}
          hint="Rows at confidence category high"
          tone="ok"
        />
      </div>

      <Panel
        className="mt-4 min-w-0"
        title="Matching detections"
        subtitle={
          observations.data
            ? `Showing the most recent ${formatCount(rows.length)} of ${formatCount(observations.data.total)}.`
            : "Most recent matches for the current query."
        }
        actions={
          <div className="flex items-center gap-2">
            <Badge tone="neutral">{formatCount(matched ?? 0)} matched</Badge>
            <a
              href={detectionExportUrl(exportParams)}
              download
              className="btn-glass inline-flex items-center gap-1.5 px-2.5 py-[4px] text-3xs"
              title="Download every match for this query as CSV"
            >
              <Download className="size-3" aria-hidden />
              Export CSV
            </a>
          </div>
        }
      >
        {observations.isError ? (
          <p className="text-2xs text-danger">Could not run this query. Check the API.</p>
        ) : null}

        {!observations.isError && rows.length === 0 && !observations.isLoading ? (
          <EmptyState
            icon={<Search className="size-4" aria-hidden />}
            title="No detections match"
            description="Widen the scope — remove the region, lower the FRP floor, or check a different period in the header."
          />
        ) : null}

        {rows.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[46rem] border-collapse text-3xs">
              <thead>
                <tr className="border-b border-line/[0.08] text-left uppercase tracking-[0.1em] text-faint">
                  <th className="py-[6px] pr-3 font-medium">Acquired (UTC)</th>
                  <th className="py-[6px] pr-3 font-medium">Sensor</th>
                  <th className="py-[6px] pr-3 font-medium">Satellite</th>
                  <th className="py-[6px] pr-3 font-medium">Latitude</th>
                  <th className="py-[6px] pr-3 font-medium">Longitude</th>
                  <th className="py-[6px] pr-3 font-medium">Confidence</th>
                  <th className="py-[6px] pr-3 font-medium">FRP</th>
                  <th className="py-[6px] font-medium">Day / night</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => setSelected(row)}
                    className="cursor-pointer border-b border-line/[0.05] text-muted transition-colors duration-150 hover:bg-line/[0.04] hover:text-ink"
                  >
                    <td className="py-[6px] pr-3 font-mono">
                      {row.acquired_at.slice(0, 16).replace("T", " ")}Z
                    </td>
                    <td className="py-[6px] pr-3">
                      <span
                        className="mr-1.5 inline-block size-1.5 rounded-full"
                        style={{
                          backgroundColor: row.sensor === "MODIS" ? "#1D4ED8" : "#15803D",
                        }}
                        aria-hidden
                      />
                      {row.sensor}
                    </td>
                    <td className="py-[6px] pr-3">{row.satellite}</td>
                    <td className="py-[6px] pr-3 font-mono">{row.latitude.toFixed(4)}</td>
                    <td className="py-[6px] pr-3 font-mono">{row.longitude.toFixed(4)}</td>
                    <td className="py-[6px] pr-3">{row.confidence_category ?? "n/a"}</td>
                    <td className="py-[6px] pr-3 font-mono">{formatFrp(row.frp_mw)}</td>
                    <td className="py-[6px]">{row.daynight === "D" ? "Day" : row.daynight === "N" ? "Night" : "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        <p className="mt-3 text-3xs font-light leading-relaxed text-faint">
          Rows are capped at 200; the matched total is exact. Click any row for its stored
          provenance. Detections are thermal anomalies, not confirmed fires.
        </p>
      </Panel>

      <ObservationDialog observation={selected} onClose={() => setSelected(null)} />
    </>
  );
}
