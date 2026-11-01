import clsx from "clsx";

import type { CalendarBucket, CalendarMetric } from "@/lib/calendarApi";
import { intensity, metricValue } from "@/lib/calendarApi";
import { formatCount, formatFrp } from "@/lib/format";
import {
  type SeverityByDay,
  maxSeverityInRange,
  severityDotClass,
  severityLabel,
} from "@/lib/severity";

function valueLabel(bucket: CalendarBucket, metric: CalendarMetric): string {
  const value = metricValue(bucket, metric);
  if (metric === "frp") return formatFrp(value);
  return formatCount(value);
}

function periodLabel(bucket: CalendarBucket, granularity: string): string {
  if (granularity === "month") {
    return new Date(`${bucket.start}T00:00:00Z`).toLocaleString("en-US", {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    });
  }
  if (granularity === "year") return bucket.start.slice(0, 4);
  return `${bucket.start} → ${bucket.end}`;
}

/** Bars for week/month/year views; a bar with no data is drawn as a hatch, not zero. */
export function CalendarBars({
  buckets,
  metric,
  granularity,
  selected,
  onSelect,
  severityByDay,
}: {
  buckets: CalendarBucket[];
  metric: CalendarMetric;
  granularity: string;
  selected: string | null;
  onSelect: (bucket: CalendarBucket) => void;
  severityByDay?: SeverityByDay;
}) {
  const max = Math.max(0, ...buckets.map((bucket) => metricValue(bucket, metric)));

  return (
    <ul className="space-y-[6px]">
      {buckets.map((bucket) => {
        const value = metricValue(bucket, metric);
        const t = intensity(value, max);
        const isSelected = selected === bucket.start;
        const severity = maxSeverityInRange(severityByDay, bucket.start, bucket.end);
        const label = periodLabel(bucket, granularity);
        return (
          <li key={bucket.start}>
            <button
              type="button"
              onClick={() => onSelect(bucket)}
              aria-pressed={isSelected}
              aria-label={`${label}: ${value} ${metric}, ${bucket.state}${
                severity ? `, anomaly ${severityLabel(severity)}` : ""
              }`}
              className={clsx(
                "group flex w-full items-center gap-3 rounded-control border border-line/[0.07] px-3 py-2 text-left transition-colors duration-150 hover:border-line/20",
                isSelected ? "border-accent/40 bg-line/[0.04]" : "",
              )}
            >
              <span className="flex w-40 shrink-0 items-center gap-1.5 font-mono text-3xs text-muted">
                {severity ? (
                  <span
                    aria-hidden
                    className={clsx("size-[6px] rounded-full", severityDotClass(severity))}
                  />
                ) : null}
                {label}
              </span>
              <span className="relative h-3 flex-1 overflow-hidden rounded-full bg-line/[0.05]">
                {bucket.state === "unobserved" ? (
                  <span
                    className="absolute inset-0 rounded-full"
                    style={{
                      backgroundImage:
                        "repeating-linear-gradient(135deg, rgba(148,163,184,0.3) 0 1px, transparent 1px 6px)",
                    }}
                  />
                ) : (
                  <span
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{
                      width: `${Math.max(t * 100, bucket.state === "quiet" ? 2 : 0)}%`,
                      backgroundColor:
                        bucket.state === "active"
                          ? `rgba(239, 68, 68, ${0.35 + t * 0.55})`
                          : "rgba(148,163,184,0.35)",
                    }}
                  />
                )}
              </span>
              <span className="w-24 shrink-0 text-right font-mono text-3xs text-muted">
                {bucket.state === "unobserved" ? "no data" : valueLabel(bucket, metric)}
              </span>
              <span
                className={clsx(
                  "w-16 shrink-0 text-right text-3xs",
                  bucket.state === "active"
                    ? "text-accent"
                    : bucket.state === "quiet"
                      ? "text-faint"
                      : "text-warn/80",
                )}
              >
                {bucket.state}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
