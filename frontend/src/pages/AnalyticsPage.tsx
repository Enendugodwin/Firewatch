import { useQuery } from "@tanstack/react-query";
import { BarChart3, Flame, TrendingUp } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel, StatTile } from "@/components/ui/Panel";
import { fetchAnalytics, trendBars } from "@/lib/analyticsApi";
import { formatCount, formatFrp, formatPercent } from "@/lib/format";
import { useModules } from "@/lib/queries";
import { useUiStore } from "@/store/ui";

function pct(value: number, total: number): number {
  return total > 0 ? value / total : 0;
}

/** One labelled proportion bar; no chart library, no invented data. */
function SplitBar({
  label,
  segments,
}: {
  label: string;
  segments: Array<{ name: string; value: number; color: string }>;
}) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  return (
    <div>
      <div className="mb-[5px] flex items-baseline justify-between">
        <span className="label">{label}</span>
        <span className="font-mono text-3xs text-faint">{formatCount(total)}</span>
      </div>
      <div className="flex h-2 overflow-hidden rounded-full bg-line/[0.06]">
        {segments.map((segment) => (
          <div
            key={segment.name}
            title={`${segment.name}: ${formatCount(segment.value)}`}
            style={{
              width: `${total > 0 ? (segment.value / total) * 100 : 0}%`,
              backgroundColor: segment.color,
            }}
          />
        ))}
      </div>
      <div className="mt-[6px] flex flex-wrap gap-x-3 gap-y-1">
        {segments.map((segment) => (
          <span key={segment.name} className="inline-flex items-center gap-1 text-3xs text-faint">
            <span
              className="size-1.5 rounded-full"
              style={{ backgroundColor: segment.color }}
              aria-hidden
            />
            {segment.name} · {formatCount(segment.value)}
          </span>
        ))}
      </div>
    </div>
  );
}

export function AnalyticsPage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "analytics");

  const analytics = useQuery({
    queryKey: ["analytics", dateRange.start, dateRange.end],
    queryFn: ({ signal }) => fetchAnalytics(dateRange.start, dateRange.end, signal),
    staleTime: 60_000,
    retry: 1,
  });

  const data = analytics.data;
  const totals = data?.totals;
  const bars = data ? trendBars(data.series) : [];
  const highShare = totals ? pct(totals.high_confidence, totals.detections) : 0;

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / History"
        title="Analytics"
        status={module?.status}
        phase={module?.phase}
        description="Trends, rankings and sensor breakdowns computed from the same stored detections as the map and calendar. Counts are detections, not fires."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Detections"
          value={formatCount(totals?.detections ?? 0)}
          hint={`${dateRange.start} → ${dateRange.end} (UTC)`}
        />
        <StatTile
          label="Active days"
          value={`${formatCount(totals?.active_days ?? 0)} / ${formatCount(totals?.days ?? 0)}`}
          hint={`Mean ${formatCount(totals?.mean_daily_detections ?? 0)} detections/day`}
          tone="ok"
        />
        <StatTile
          label="FRP sum"
          value={formatFrp(totals?.frp_sum_mw ?? 0)}
          hint={`Peak detection ${formatFrp(totals?.frp_max_mw ?? null)}`}
        />
        <StatTile
          label="High confidence"
          value={formatPercent(highShare)}
          hint={`${formatCount(totals?.high_confidence ?? 0)} detections at category high`}
          tone="info"
        />
      </div>

      {analytics.isError ? (
        <Panel className="mt-4" title="Analytics unavailable">
          <p className="text-2xs text-danger">The summary could not be loaded. Check the API.</p>
        </Panel>
      ) : null}

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Panel
          title="Daily trend"
          subtitle="Every day in the period; empty days are drawn at zero."
          actions={
            <span className="inline-flex items-center gap-1.5 text-3xs text-faint">
              <TrendingUp className="size-3" aria-hidden />
              detections per day
            </span>
          }
        >
          {analytics.isLoading ? (
            <p className="py-10 text-center text-2xs text-muted">Loading trend…</p>
          ) : bars.length === 0 ? (
            <EmptyState
              icon={<BarChart3 className="size-4" aria-hidden />}
              title="No days in this period"
              description="Choose a wider period in the header."
            />
          ) : (
            <div className="flex h-44 items-end justify-between gap-[3px]" role="img" aria-label="Daily detections">
              {bars.map((point) => (
                <div key={point.date} className="group relative flex h-full w-full items-end">
                  <div
                    className="w-full rounded-t-[2px] bg-fire-medium/80 transition-colors duration-150 group-hover:bg-fire-high"
                    style={{
                      height: `${Math.max(point.ratio * 100, point.detections > 0 ? 3 : 1)}%`,
                      maxWidth: 42,
                    }}
                    title={`${point.date}: ${formatCount(point.detections)} detections`}
                  />
                </div>
              ))}
            </div>
          )}
          {bars.length > 0 ? (
            <div className="mt-[6px] flex justify-between font-mono text-3xs text-faint">
              <span>{bars[0]?.date}</span>
              <span>{bars[bars.length - 1]?.date}</span>
            </div>
          ) : null}
        </Panel>

        <Panel title="Breakdowns" subtitle="Share of the same filtered detections.">
          <div className="space-y-4">
            <SplitBar
              label="Sensor"
              segments={[
                { name: "MODIS", value: totals?.modis ?? 0, color: "#1D4ED8" },
                { name: "VIIRS", value: totals?.viirs ?? 0, color: "#15803D" },
              ]}
            />
            <SplitBar
              label="Day / night"
              segments={[
                { name: "Day", value: data?.daynight.D ?? 0, color: "#F59E0B" },
                { name: "Night", value: data?.daynight.N ?? 0, color: "#6366F1" },
                { name: "Unknown", value: data?.daynight.unknown ?? 0, color: "#475569" },
              ]}
            />
            <SplitBar
              label="Confidence"
              segments={[
                { name: "High", value: data?.confidence.high ?? 0, color: "#10B981" },
                { name: "Nominal", value: data?.confidence.nominal ?? 0, color: "#F59E0B" },
                { name: "Low", value: data?.confidence.low ?? 0, color: "#EF4444" },
                { name: "Unknown", value: data?.confidence.unknown ?? 0, color: "#475569" },
              ]}
            />
          </div>
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Panel
          title="Top activity cells"
          subtitle={
            data
              ? `Ranked by detections on a ${data.cell_degrees}° grid — cells, not countries.`
              : undefined
          }
        >
          {analytics.isLoading ? (
            <p className="py-10 text-center text-2xs text-muted">Loading rankings…</p>
          ) : data && data.top_cells.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[28rem] border-collapse text-3xs">
                <thead>
                  <tr className="border-b border-line/[0.08] text-left uppercase tracking-[0.1em] text-faint">
                    <th className="py-[6px] pr-3 font-medium">Latitude</th>
                    <th className="py-[6px] pr-3 font-medium">Longitude</th>
                    <th className="py-[6px] pr-3 text-right font-medium">Detections</th>
                    <th className="py-[6px] text-right font-medium">FRP sum</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_cells.map((cell) => (
                    <tr
                      key={`${cell.latitude},${cell.longitude}`}
                      className="border-b border-line/[0.05] text-muted"
                    >
                      <td className="py-[6px] pr-3 font-mono">{cell.latitude.toFixed(2)}</td>
                      <td className="py-[6px] pr-3 font-mono">{cell.longitude.toFixed(2)}</td>
                      <td className="py-[6px] pr-3 text-right font-mono">
                        {formatCount(cell.detections)}
                      </td>
                      <td className="py-[6px] text-right font-mono">
                        {formatFrp(cell.frp_sum_mw)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              icon={<Flame className="size-4" aria-hidden />}
              title="No detections in this period"
              description="Nothing was stored for this scope, so there is nothing to rank."
            />
          )}
        </Panel>

        <Panel title="Satellites" subtitle="Which platform produced the detections.">
          {analytics.isLoading ? (
            <p className="text-2xs text-muted">Loading…</p>
          ) : data && data.satellites.length > 0 ? (
            <ul className="space-y-[6px]">
              {data.satellites.map((item) => (
                <li
                  key={item.satellite}
                  className="flex items-center justify-between gap-3 border-b border-line/[0.05] py-[5px] last:border-0"
                >
                  <span className="text-2xs text-muted">{item.satellite}</span>
                  <span className="font-mono text-3xs text-faint">
                    {formatCount(item.detections)} · {formatFrp(item.frp_sum_mw)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-2xs text-muted">No detections.</p>
          )}
        </Panel>
      </div>

      {data ? (
        <p className="mt-4 text-3xs font-light leading-relaxed text-faint">
          {data.notes.join(" ")}
        </p>
      ) : null}
    </>
  );
}
