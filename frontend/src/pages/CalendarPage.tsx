import { useQuery } from "@tanstack/react-query";
import { CalendarDays, ChevronLeft, ChevronRight, Flame, Info, X } from "lucide-react";
import { useMemo, useState } from "react";

import { BucketPanel } from "@/components/calendar/BucketPanel";
import { CalendarBars } from "@/components/calendar/CalendarBars";
import { CalendarHeat } from "@/components/calendar/CalendarHeat";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel, StatTile } from "@/components/ui/Panel";
import {
  type CalendarBucket,
  type CalendarGranularity,
  type CalendarMetric,
  METRIC_LABEL,
  fetchCalendar,
  fetchCalendarDrilldown,
  fetchCalendarMonths,
  metricValue,
} from "@/lib/calendarApi";
import { formatCount, formatFrp } from "@/lib/format";
import { useModules } from "@/lib/queries";
import { useUiStore } from "@/store/ui";

const GRANULARITIES: { value: CalendarGranularity; label: string; hint: string }[] = [
  { value: "day", label: "Day", hint: "One cell per day" },
  { value: "week", label: "Week", hint: "Monday-based weeks" },
  { value: "month", label: "Month", hint: "Calendar months" },
  { value: "year", label: "Year", hint: "Calendar years" },
];

const METRICS: CalendarMetric[] = ["detections", "frp", "high_confidence"];
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function monthTitle(key: string): string {
  const year = Number(key.slice(0, 4));
  const month = Number(key.slice(5, 7));
  return `${MONTH_NAMES[month - 1]} ${year}`;
}

function monthBounds(key: string): { start: string; end: string } {
  const year = Number(key.slice(0, 4));
  const month = Number(key.slice(5, 7));
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return {
    start: `${key}-01`,
    end: `${key}-${String(last).padStart(2, "0")}`,
  };
}

function monthsBack(endDate: string, count: number): string {
  const date = new Date(`${endDate}T00:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() - count + 1);
  date.setUTCDate(1);
  return date.toISOString().slice(0, 10);
}

export function CalendarPage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "calendar");

  const [granularity, setGranularity] = useState<CalendarGranularity>("day");
  const [metric, setMetric] = useState<CalendarMetric>("detections");
  const [selected, setSelected] = useState<CalendarBucket | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [viewMonth, setViewMonth] = useState<string | null>(null);

  // The picker offers only months that hold data, within a 12-month lookback.
  const monthsQuery = useQuery({
    queryKey: ["calendar", "months", dateRange.end],
    queryFn: ({ signal }) =>
      fetchCalendarMonths(monthsBack(dateRange.end, 12), dateRange.end, signal),
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const months = monthsQuery.data ?? [];

  const activeRange = useMemo(() => {
    if (!viewMonth) return { start: dateRange.start, end: dateRange.end };
    return monthBounds(viewMonth);
  }, [viewMonth, dateRange.start, dateRange.end]);

  const query = useMemo(
    () => ({
      startDate: activeRange.start,
      endDate: activeRange.end,
      granularity,
      synthetic: false,
    }),
    [activeRange.start, activeRange.end, granularity],
  );

  const calendar = useQuery({
    queryKey: ["calendar", query],
    queryFn: ({ signal }) => fetchCalendar(query, signal),
    staleTime: 30_000,
    retry: 1,
  });

  const drilldown = useQuery({
    queryKey: ["calendar", "drilldown", selected?.start ?? null, query],
    queryFn: ({ signal }) => fetchCalendarDrilldown(selected!.start, query, signal),
    enabled: Boolean(selected),
    staleTime: 30_000,
    retry: 1,
  });

  const buckets = calendar.data?.buckets ?? [];
  const totals = calendar.data?.totals;
  const peak = buckets.reduce((max, bucket) => Math.max(max, metricValue(bucket, metric)), 0);
  const unobserved = totals?.unobserved_buckets ?? 0;
  const monthIndex = months.findIndex((entry) => entry.month === viewMonth);

  function select(bucket: CalendarBucket) {
    setSelectedId(null);
    setSelected((current) => (current?.start === bucket.start ? null : bucket));
  }

  function stepMonth(direction: -1 | 1) {
    if (months.length === 0) return;
    const nextIndex =
      monthIndex === -1
        ? direction === -1
          ? months.length - 1
          : 0
        : Math.min(months.length - 1, Math.max(0, monthIndex + direction));
    setViewMonth(months[nextIndex]!.month);
    setSelected(null);
  }

  return (
    <>
      <div className="relative z-20">
        <PageHeader
          eyebrow="Firewatch X / History"
          title="Burning Calendar"
          status={module?.status}
          phase={module?.phase}
          description="Stored detections rolled into days, weeks, months or years. Every period in the range is present: an empty period is either a checked zero or an explicit gap in source coverage."
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <div
                role="group"
                aria-label="Granularity"
                className="inline-flex rounded-full border border-line/[0.1] p-[2px]"
              >
                {GRANULARITIES.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    title={item.hint}
                    aria-pressed={granularity === item.value}
                    onClick={() => {
                      setGranularity(item.value);
                      setSelected(null);
                    }}
                    className={`rounded-full px-3 py-[5px] text-3xs uppercase tracking-[0.12em] transition-colors duration-150 ${
                      granularity === item.value
                        ? "bg-line/[0.09] text-ink"
                        : "text-faint hover:text-muted"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <label className="inline-flex items-center gap-2 text-3xs uppercase tracking-[0.12em] text-faint">
                Metric
                <select
                  value={metric}
                  onChange={(event) => setMetric(event.target.value as CalendarMetric)}
                  className="rounded-control border border-line/10 bg-canvas/70 px-2 py-[5px] font-mono text-3xs uppercase tracking-[0.08em] text-ink"
                >
                  {METRICS.map((item) => (
                    <option key={item} value={item}>
                      {METRIC_LABEL[item]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          }
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Detections in range"
          value={formatCount(totals?.detections ?? 0)}
          hint={`${activeRange.start} -> ${activeRange.end} (UTC)`}
        />
        <StatTile
          label="Active periods"
          value={`${formatCount(totals?.active_buckets ?? 0)} / ${formatCount(totals?.buckets ?? 0)}`}
          hint="Buckets with at least one detection"
          tone="ok"
        />
        <StatTile
          label="FRP sum"
          value={formatFrp(totals?.frp_sum_mw ?? 0)}
          hint={`Summed over every detection, peak ${formatFrp(totals?.frp_max_mw ?? null)}`}
        />
        <StatTile
          label="Periods without data"
          value={formatCount(unobserved)}
          hint="No availability recorded, never counted as zero"
          tone={unobserved > 0 ? "warn" : "neutral"}
        />
      </div>

      {calendar.isError ? (
        <Panel className="mt-4" title="Calendar unavailable">
          <p className="text-2xs text-danger">
            The calendar could not be loaded. Check the API and try again.
          </p>
        </Panel>
      ) : null}

      <Panel
        className="mt-4 min-w-0"
        title={`${granularity === "day" ? "Daily" : granularity === "week" ? "Weekly" : granularity === "month" ? "Monthly" : "Annual"} activity · ${METRIC_LABEL[metric]}`}
        subtitle={
          peak > 0
            ? `Shaded by ${METRIC_LABEL[metric].toLowerCase()}. Hatched cells have no availability record.`
            : "No detections in this range for the current filters."
        }
        actions={
          <div className="flex flex-wrap items-center gap-2 text-3xs text-faint">
            <span className="inline-flex items-center gap-1">
              <span className="size-2 rounded-[2px] bg-[rgba(239,68,68,0.75)]" aria-hidden />
              detections
            </span>
            <span className="inline-flex items-center gap-1">
              <span
                className="size-2 rounded-[2px] border border-line/20"
                aria-hidden
                style={{ backgroundColor: "rgba(148,163,184,0.12)" }}
              />
              observed, none
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2 rounded-[2px] border border-dashed border-line/25" aria-hidden />
              no data
            </span>
          </div>
        }
      >
        {granularity === "day" ? (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-1 rounded-full border border-line/[0.1] p-[2px]">
              <button
                type="button"
                onClick={() => stepMonth(-1)}
                disabled={months.length === 0}
                aria-label="Previous month"
                className="rounded-full p-1.5 text-faint transition-colors duration-150 hover:text-ink disabled:opacity-30"
              >
                <ChevronLeft className="size-3.5" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => stepMonth(1)}
                disabled={months.length === 0}
                aria-label="Next month"
                className="rounded-full p-1.5 text-faint transition-colors duration-150 hover:text-ink disabled:opacity-30"
              >
                <ChevronRight className="size-3.5" aria-hidden />
              </button>
            </div>

            <button
              type="button"
              onClick={() => {
                setViewMonth(null);
                setSelected(null);
              }}
              aria-pressed={viewMonth === null}
              className={`rounded-full border px-3 py-[4px] text-3xs transition-colors duration-150 ${
                viewMonth === null
                  ? "border-line/25 bg-line/[0.08] text-ink"
                  : "border-line/10 text-faint hover:text-muted"
              }`}
            >
              Header range
            </button>

            <div className="flex flex-wrap items-center gap-1">
              {months.map((entry) => (
                <button
                  key={entry.month}
                  type="button"
                  onClick={() => {
                    setViewMonth(entry.month);
                    setSelected(null);
                  }}
                  aria-pressed={viewMonth === entry.month}
                  title={`${entry.detections.toLocaleString("en-US")} detections · ${entry.observed_days} observed days`}
                  className={`rounded-full border px-3 py-[4px] text-3xs transition-colors duration-150 ${
                    viewMonth === entry.month
                      ? "border-accent/40 bg-accent/[0.10] text-ink"
                      : "border-line/10 text-muted hover:border-line/25 hover:text-ink"
                  }`}
                >
                  {monthTitle(entry.month)}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {calendar.isLoading ? (
          <p className="text-2xs text-muted">Loading buckets…</p>
        ) : buckets.length === 0 ? (
          <EmptyState
            icon={<CalendarDays className="size-4" aria-hidden />}
            title="No buckets for this range"
            description="Pick a different period in the header, or choose another month above."
          />
        ) : granularity === "day" ? (
          <CalendarHeat
            buckets={buckets}
            metric={metric}
            selected={selected?.start ?? null}
            onSelect={select}
            granularity={granularity}
          />
        ) : (
          <CalendarBars
            buckets={buckets}
            metric={metric}
            granularity={granularity}
            selected={selected?.start ?? null}
            onSelect={select}
          />
        )}

        {!selected ? (
          <p className="mt-4 border-t border-line/[0.07] pt-3 text-3xs font-light leading-relaxed text-faint">
            <Info className="mr-1 inline size-3 align-[-2px]" aria-hidden />
            Select any day, week, month or year to inspect the detections behind it.
            <Flame className="ml-3 mr-1 inline size-3 align-[-2px] text-fire-medium" aria-hidden />
            Counts are detections, not fires. Empty periods are labelled{" "}
            <Badge tone="neutral">quiet</Badge> (observed, nothing seen) or{" "}
            <Badge tone="warn">unobserved</Badge> (no data recorded).
          </p>
        ) : null}
      </Panel>

      {selected ? (
        <div className="fixed inset-0 z-40 flex justify-end">
          <button
            type="button"
            aria-label="Close bucket detail"
            onClick={() => {
              setSelected(null);
              setSelectedId(null);
            }}
            className="absolute inset-0 bg-[#05070F]/50 backdrop-blur-[2px]"
          />
          <div className="relative z-10 flex h-full w-full max-w-[26rem] flex-col p-3 sm:p-4">
            <div className="mb-2 flex items-center justify-end">
              <button
                type="button"
                onClick={() => {
                  setSelected(null);
                  setSelectedId(null);
                }}
                aria-label="Close panel"
                className="rounded-full border border-line/15 p-1.5 text-faint hover:text-ink"
              >
                <X className="size-3.5" aria-hidden />
              </button>
            </div>
            <div className="min-h-0 flex-1">
              <BucketPanel
                bucketStart={selected.start}
                data={drilldown.data}
                loading={drilldown.isLoading}
                error={drilldown.isError ? "Could not load this bucket." : null}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onClose={() => {
                  setSelected(null);
                  setSelectedId(null);
                }}
              />
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
