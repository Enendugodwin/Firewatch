import { type UseQueryResult, useQuery } from "@tanstack/react-query";
import { Activity, CalendarRange, Info, TrendingDown, TrendingUp } from "lucide-react";
import { useMemo } from "react";

import { Badge, type Tone } from "@/components/ui/Badge";
import { LoadingBlock } from "@/components/ui/LoadingCue";
import { Panel } from "@/components/ui/Panel";
import {
  type CalendarIntelligence as CalendarIntelligencePayload,
  type CalendarMetric,
  type CalendarQuery,
  type SeasonalityBlock,
  type TrendPoint,
  fetchCalendarIntelligence,
} from "@/lib/calendarApi";
import { formatCount, formatFrp } from "@/lib/format";

const SEVERITY_TONE: Record<string, Tone> = {
  critical: "danger",
  high: "warn",
  moderate: "info",
  below_baseline: "neutral",
  unknown_scale: "neutral",
  normal: "neutral",
  unobserved: "neutral",
};

const DIRECTION_TONE: Record<string, Tone> = {
  rising: "fire",
  falling: "info",
  flat: "neutral",
  unknown: "neutral",
};

export function metricLabel(metric: CalendarMetric): string {
  if (metric === "frp") return "MW";
  return metric === "high_confidence" ? "high-confidence detections" : "detections";
}

export function formatMetric(value: number | null, metric: CalendarMetric): string {
  if (value === null) return "—";
  return metric === "frp" ? formatFrp(value) : formatCount(value);
}

export interface SparklineGeometry {
  width: number;
  height: number;
  /** One path per contiguous run of observed days; a gap starts a new path. */
  linePaths: string[];
  meanPaths: string[];
  dots: Array<{ date: string; x: number; y: number; severity: string }>;
  max: number;
}

/**
 * Build the SVG geometry for the daily series.
 *
 * Missing days break the path rather than being drawn as zero: a gap must look
 * like a gap, not like a collapse to no activity.
 */
export function buildSparkline(
  series: TrendPoint[],
  width = 640,
  height = 72,
  pad = 6,
): SparklineGeometry {
  const max = Math.max(
    0,
    ...series.map((point) => point.value ?? 0),
    ...series.map((point) => point.trailing_mean ?? 0),
  );
  const span = Math.max(1, series.length - 1);
  const xFor = (index: number) => pad + (index / span) * (width - pad * 2);
  const yFor = (value: number) =>
    max <= 0 ? height - pad : height - pad - (value / max) * (height - pad * 2);

  const linePaths: string[] = [];
  const meanPaths: string[] = [];
  const dots: SparklineGeometry["dots"] = [];
  let lineRun: Array<[number, number]> = [];
  let meanRun: Array<[number, number]> = [];

  const toPath = (points: Array<[number, number]>) => {
    if (points.length === 0) return null;
    if (points.length === 1) {
      const [x, y] = points[0]!;
      // A single observed day is a point, not a line: draw a degenerate
      // segment so the round line cap still renders a visible mark.
      return `M${x} ${y} L${x} ${y}`;
    }
    return points
      .map(([x, y], index) => `${index === 0 ? "M" : "L"}${x} ${y}`)
      .join(" ");
  };

  const flush = () => {
    const line = toPath(lineRun);
    const mean = toPath(meanRun);
    if (line) linePaths.push(line);
    if (mean) meanPaths.push(mean);
    lineRun = [];
    meanRun = [];
  };

  series.forEach((point, index) => {
    const x = xFor(index);
    if (point.value === null) {
      flush();
      return;
    }
    lineRun.push([Number(x.toFixed(2)), Number(yFor(point.value).toFixed(2))]);
    if (point.trailing_mean !== null) {
      meanRun.push([Number(x.toFixed(2)), Number(yFor(point.trailing_mean).toFixed(2))]);
    }
    if (["moderate", "high", "critical"].includes(point.severity)) {
      dots.push({
        date: point.date,
        x: Number(x.toFixed(2)),
        y: Number(yFor(point.value).toFixed(2)),
        severity: point.severity,
      });
    }
  });
  flush();

  return { width, height, linePaths, meanPaths, dots, max };
}

export function seasonBarHeight(month: SeasonalityBlock["months"][number], maxIndex: number) {
  if (month.index !== null && Number.isFinite(month.index)) {
    return Math.max(4, Math.min(100, (month.index / Math.max(1, maxIndex)) * 100));
  }
  return month.sufficient ? 12 : 6;
}

/** Shared query so the grid, the bars and the panel read one result, not three. */
export function useCalendarIntelligence(query: CalendarQuery, metric: CalendarMetric) {
  return useQuery({
    queryKey: ["calendar", "intelligence", query, metric],
    queryFn: ({ signal }) => fetchCalendarIntelligence(query, { metric }, signal),
    staleTime: 60_000,
    retry: 1,
  });
}

export function CalendarIntelligence({
  intelligence,
  metric,
  onOpenDay,
}: {
  intelligence: UseQueryResult<CalendarIntelligencePayload>;
  metric: CalendarMetric;
  onOpenDay: (day: string) => void;
}) {
  const data = intelligence.data;
  const geometry = useMemo(
    () => buildSparkline(data?.trend?.series ?? []),
    [data?.trend?.series],
  );
  const maxIndex = data
    ? Math.max(1, ...data.seasonality.months.map((month) => month.index ?? 1))
    : 1;

  return (
    <Panel
      className="mt-4 min-w-0"
      title="Trends, anomalies & seasonality"
      subtitle="Computed over the same window as the calendar. Each method states what it could not measure."
      actions={
        data ? <Badge tone="neutral">{data.method.version ?? "calendar-intel"}</Badge> : null
      }
    >
      {intelligence.isLoading ? (
        <LoadingBlock
          label="Computing trend, anomaly baseline and seasonal profile…"
          lines={4}
        />
      ) : intelligence.isError ? (
        <p className="text-2xs text-danger">
          The intelligence panel could not be loaded. The calendar above is unaffected.
        </p>
      ) : !data ? (
        <p className="text-2xs text-muted">No intelligence result for this window.</p>
      ) : !data.trend || !data.seasonality ? (
        <p className="text-2xs text-warn">
          The intelligence payload is incomplete. The calendar above is unaffected.
        </p>
      ) : (
        <div className="space-y-6">
          <p className="text-3xs font-light text-faint">
            {formatCount(data.window.observed_days)} observed of {formatCount(data.window.days)} days
            {" · "}
            {formatCount(data.window.missing_days)} missing (excluded, never zero)
            {" · "}
            history from {data.window.history_start}
          </p>

          {/* ---- Trend ------------------------------------------------ */}
          <section aria-labelledby="calendar-trend-heading">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <h3 id="calendar-trend-heading" className="label">
                Trend
              </h3>
              {data.trend.status === "ok" ? (
                <>
                  <Badge tone={DIRECTION_TONE[data.trend.direction] ?? "neutral"}>
                    {data.trend.direction === "rising" ? (
                      <TrendingUp className="size-3" aria-hidden />
                    ) : data.trend.direction === "falling" ? (
                      <TrendingDown className="size-3" aria-hidden />
                    ) : (
                      <Activity className="size-3" aria-hidden />
                    )}
                    {data.trend.direction}
                  </Badge>
                  <Badge tone={data.trend.confidence === "low" ? "warn" : "neutral"}>
                    {data.trend.confidence} confidence
                  </Badge>
                  <span className="font-mono text-3xs text-faint">
                    Theil–Sen · {data.trend.observations} observed days · {Math.round(data.trend.coverage * 100)}% coverage
                  </span>
                </>
              ) : (
                <Badge tone="warn">insufficient history</Badge>
              )}
            </div>

            {data.trend.status === "ok" ? (
              <>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-card border border-line/[0.07] bg-line/[0.02] px-3 py-2">
                    <div className="text-3xs uppercase tracking-[0.1em] text-faint">Slope / 30 days</div>
                    <div className="mt-1 font-mono text-sm text-ink">
                      {data.trend.slope_per_30_days! >= 0 ? "+" : ""}
                      {data.trend.slope_per_30_days!.toFixed(1)} {metricLabel(metric)}
                    </div>
                  </div>
                  <div className="rounded-card border border-line/[0.07] bg-line/[0.02] px-3 py-2">
                    <div className="text-3xs uppercase tracking-[0.1em] text-faint">First → last</div>
                    <div className="mt-1 font-mono text-sm text-ink">
                      {data.trend.change_ratio === null
                        ? "—"
                        : `${data.trend.change_ratio.toFixed(2)}×`}
                    </div>
                  </div>
                  <div className="rounded-card border border-line/[0.07] bg-line/[0.02] px-3 py-2">
                    <div className="text-3xs uppercase tracking-[0.1em] text-faint">Median level</div>
                    <div className="mt-1 font-mono text-sm text-ink">
                      {formatMetric(data.trend.level_median ?? null, metric)}
                    </div>
                  </div>
                </div>

                <svg
                  viewBox={`0 0 ${geometry.width} ${geometry.height}`}
                  className="mt-3 h-[86px] w-full"
                  role="img"
                  aria-label={`Daily ${metricLabel(metric)} with a 7-observed-day trailing mean; ${geometry.dots.length} anomalies marked.`}
                >
                  {geometry.meanPaths.map((path, index) => (
                    <path
                      key={`mean-${index}`}
                      d={path}
                      fill="none"
                      stroke="rgba(148,163,184,0.55)"
                      strokeWidth={1.5}
                      strokeDasharray="4 3"
                    />
                  ))}
                  {geometry.linePaths.map((path, index) => (
                    <path
                      key={`line-${index}`}
                      d={path}
                      fill="none"
                      stroke="#ef4444"
                      strokeWidth={1.6}
                      strokeLinejoin="round"
                    />
                  ))}
                  {geometry.dots.map((dot) => (
                    <circle
                      key={dot.date}
                      cx={dot.x}
                      cy={dot.y}
                      r={dot.severity === "critical" ? 3.2 : 2.4}
                      fill={dot.severity === "critical" ? "#f87171" : "#fbbf24"}
                      aria-hidden
                    />
                  ))}
                </svg>

                <div className="mt-1 flex flex-wrap items-center gap-3 text-3xs text-faint">
                  <span className="inline-flex items-center gap-1">
                    <span className="h-[2px] w-4 bg-[#ef4444]" aria-hidden /> daily
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="h-[2px] w-4 border-t border-dashed border-[rgba(148,163,184,0.7)]" aria-hidden />
                    7-day trailing mean
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="size-1.5 rounded-full bg-[#fbbf24]" aria-hidden /> anomaly
                  </span>
                </div>
              </>
            ) : (
              <p className="rounded-card border border-warn/20 bg-warn/[0.04] px-3 py-2 text-2xs font-light leading-relaxed text-muted">
                {data.trend.requirements.note}
              </p>
            )}
          </section>

          {/* ---- Anomalies -------------------------------------------- */}
          <section aria-labelledby="calendar-anomalies-heading">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <h3 id="calendar-anomalies-heading" className="label">
                Anomalies
              </h3>
              <Badge tone={data.anomalies.count > 0 ? "warn" : "ok"}>
                {data.anomalies.count} flagged
              </Badge>
              <span className="text-3xs text-faint">
                robust z ≥ 3 · baseline: {data.anomalies.baseline?.median?.toFixed(1) ?? "—"} {" "}
                {metricLabel(metric)} over {data.anomalies.baseline?.days ?? 0} days
              </span>
            </div>

            {data.anomalies.status === "insufficient_history" ? (
              <p className="text-2xs font-light text-muted">
                {data.anomalies.requirements?.note ??
                  "No baseline is available for this window, so no anomaly is claimed."}
              </p>
            ) : data.anomalies.items.length === 0 ? (
              <p className="text-2xs font-light text-muted">
                No observed day exceeds the anomaly threshold in this window.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {data.anomalies.items.slice(0, 5).map((item) => (
                  <li key={item.date}>
                    <button
                      type="button"
                      onClick={() => onOpenDay(item.date)}
                      className="flex w-full items-start justify-between gap-3 rounded-card border border-line/[0.07] px-3 py-2 text-left transition-colors duration-150 hover:border-line/20"
                    >
                      <span className="min-w-0">
                        <span className="font-mono text-3xs text-ink">{item.date}</span>
                        <span className="ml-2 text-2xs font-light text-muted">
                          {formatMetric(item.observed, metric)} vs expected {formatMetric(item.expected, metric)}
                          {item.robust_z === null ? "" : ` · z ${item.robust_z.toFixed(1)}`}
                        </span>
                      </span>
                      <Badge tone={SEVERITY_TONE[item.severity] ?? "neutral"}>{item.severity}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {data.anomalies.items.length > 5 ? (
              <p className="mt-1.5 text-3xs text-faint">
                Showing the 5 strongest; {data.anomalies.count - 5} more in this window.
              </p>
            ) : null}
          </section>

          {/* ---- Seasonality ------------------------------------------ */}
          <section aria-labelledby="calendar-season-heading">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <h3 id="calendar-season-heading" className="label">
                Seasonal pattern
              </h3>
              <Badge
                tone={
                  data.seasonality.status === "ok"
                    ? "ok"
                    : data.seasonality.status === "partial"
                      ? "warn"
                      : "neutral"
                }
              >
                {data.seasonality.status.replace("_", " ")}
              </Badge>
              <span className="text-3xs text-faint">
                {data.seasonality.years.length > 0
                  ? `years ${data.seasonality.years.join(", ")}`
                  : "no years with observations"}
                {" · "}
                {data.seasonality.sufficient_months}/12 months with ≥2 years
              </span>
            </div>

            <div className="flex items-end gap-1" role="img" aria-label="Monthly seasonal profile">
              {data.seasonality.months.map((month) => (
                <div key={month.month} className="flex min-w-0 flex-1 flex-col items-center gap-1">
                  <div className="flex h-[72px] w-full items-end">
                    <div
                      title={
                        !month.sufficient
                          ? `${month.label}: not enough multi-year coverage`
                          : `${month.label}: ${month.mean?.toFixed(1) ?? "—"} (${month.years} year${month.years === 1 ? "" : "s"})`
                      }
                      className={
                        month.sufficient
                          ? "w-full rounded-t-[2px] bg-accent/60"
                          : "w-full rounded-t-[2px] border border-dashed border-line/25 bg-line/[0.03]"
                      }
                      style={{ height: `${seasonBarHeight(month, maxIndex)}%` }}
                    />
                  </div>
                  <span className="text-[9px] uppercase tracking-[0.06em] text-faint">
                    {month.label}
                  </span>
                </div>
              ))}
            </div>

            {data.seasonality.status === "ok" ? (
              <p className="mt-2 text-2xs font-light text-muted">
                Peak {data.seasonality.peak_month} · trough {data.seasonality.trough_month}
                {data.seasonality.seasonal_amplitude !== null
                  ? ` · amplitude ${data.seasonality.seasonal_amplitude.toFixed(1)}×`
                  : ""}
              </p>
            ) : null}

            <p className="mt-2 flex items-start gap-1.5 rounded-card border border-line/[0.07] bg-line/[0.02] px-3 py-2 text-3xs font-light leading-relaxed text-muted">
              <Info className="mt-[1px] size-3 shrink-0 text-faint" aria-hidden />
              {data.seasonality.requirements.note}
            </p>
          </section>

          <p className="flex items-start gap-1.5 border-t border-line/[0.07] pt-3 text-3xs font-light leading-relaxed text-faint">
            <CalendarRange className="mt-[1px] size-3 shrink-0" aria-hidden />
            {data.notes.join(" ")}
          </p>
        </div>
      )}
    </Panel>
  );
}
