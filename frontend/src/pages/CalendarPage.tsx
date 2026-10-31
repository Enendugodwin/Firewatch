import { useQuery } from "@tanstack/react-query";
import { CalendarDays, Flame, Highlighter, Info } from "lucide-react";
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

export function CalendarPage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "calendar");

  const [granularity, setGranularity] = useState<CalendarGranularity>("day");
  const [metric, setMetric] = useState<CalendarMetric>("detections");
  const [selected, setSelected] = useState<CalendarBucket | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const query = useMemo(
    () => ({
      startDate: dateRange.start,
      endDate: dateRange.end,
      granularity,
      synthetic: false,
    }),
    [dateRange.start, dateRange.end, granularity],
  );

  const calendar = useQuery({
    queryKey: ["calendar", query],
    queryFn: ({ signal }) => fetchCalendar(query, signal),
    staleTime: 30_000,
    retry: 1,
  });

  const drilldown = useQuery({
    queryKey: ["calendar", "drilldown", selected?.start ?? null, query],
    queryFn: ({ signal }) =>
      fetchCalendarDrilldown(selected!.start, query, signal),
    enabled: Boolean(selected),
    staleTime: 30_000,
    retry: 1,
  });

  const buckets = calendar.data?.buckets ?? [];
  const totals = calendar.data?.totals;
  const peak = buckets.reduce((max, bucket) => Math.max(max, metricValue(bucket, metric)), 0);

  function select(bucket: CalendarBucket) {
    setSelectedId(null);
    setSelected((current) => (current?.start === bucket.start ? null : bucket));
  }

  const unobserved = totals?.unobserved_buckets ?? 0;

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
          hint={`${dateRange.start} → ${dateRange.end} (UTC)`}
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
          hint={`Summed over every detection · peak ${formatFrp(totals?.frp_max_mw ?? null)}`}
        />
        <StatTile
          label="Periods without data"
          value={formatCount(unobserved)}
          hint="No availability recorded — never counted as zero"
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

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Panel
          className="min-w-0"
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
                <span
                  className="size-2 rounded-[2px] border border-dashed border-line/25"
                  aria-hidden
                />
                no data
              </span>
            </div>
          }
        >
          {calendar.isLoading ? (
            <p className="text-2xs text-muted">Loading buckets…</p>
          ) : buckets.length === 0 ? (
            <EmptyState
              icon={<CalendarDays className="size-4" aria-hidden />}
              title="No buckets for this range"
              description="Pick a different period in the header; buckets are always materialised for the full range."
            />
          ) : granularity === "day" ? (
            <CalendarHeat
              buckets={buckets}
              metric={metric}
              selected={selected?.start ?? null}
              onSelect={select}
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
        </Panel>

        {selected ? (
          <div className="min-h-[24rem] xl:h-[calc(100vh-22rem)]">
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
        ) : (
          <Panel title="Drill down" className="h-fit min-w-0">
            <div className="space-y-3 text-2xs font-light leading-relaxed text-muted">
              <p>
                <Info className="mr-1 inline size-3 align-[-2px] text-faint" aria-hidden />
                Select any day, week, month or year to see the detections behind it.
              </p>
              <p>
                <Flame className="mr-1 inline size-3 align-[-2px] text-fire-medium" aria-hidden />
                Counts are detections, not fires. FRP is summed from the stored per-detection
                measurements.
              </p>
              <p>
                <Highlighter className="mr-1 inline size-3 align-[-2px] text-faint" aria-hidden />
                Empty periods are labelled: <Badge tone="neutral">quiet</Badge> means a source
                looked and saw nothing; <Badge tone="warn">unobserved</Badge> means no data exists.
              </p>
            </div>
          </Panel>
        )}
      </div>
    </>
  );
}
