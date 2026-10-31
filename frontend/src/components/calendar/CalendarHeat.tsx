import clsx from "clsx";

import type { CalendarBucket, CalendarMetric } from "@/lib/calendarApi";
import { intensity, metricValue } from "@/lib/calendarApi";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface MonthGroup {
  key: string;
  label: string;
  weeks: Array<Array<CalendarBucket | null>>;
}

function monthLabel(date: Date): string {
  return date.toLocaleString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
}

/** Group day buckets into Monday-first weeks, one group per month. */
export function groupIntoMonths(buckets: CalendarBucket[]): MonthGroup[] {
  const groups = new Map<string, MonthGroup>();
  for (const bucket of buckets) {
    const date = new Date(`${bucket.start}T00:00:00Z`);
    const key = bucket.start.slice(0, 7);
    let group = groups.get(key);
    if (!group) {
      group = { key, label: monthLabel(date), weeks: [] };
      groups.set(key, group);
    }

    const weekday = (date.getUTCDay() + 6) % 7;
    let week = group.weeks[group.weeks.length - 1];
    if (!week || week[weekday] !== null) {
      week = Array.from({ length: 7 }, () => null);
      group.weeks.push(week);
    }
    week[weekday] = bucket;
  }
  return [...groups.values()];
}

export function CalendarHeat({
  buckets,
  metric,
  selected,
  onSelect,
}: {
  buckets: CalendarBucket[];
  metric: CalendarMetric;
  selected: string | null;
  onSelect: (bucket: CalendarBucket) => void;
}) {
  const groups = groupIntoMonths(buckets);
  const max = Math.max(0, ...buckets.map((bucket) => metricValue(bucket, metric)));

  return (
    <div className="space-y-5">
      {groups.map((group) => (
        <div key={group.key}>
          <div className="mb-2 flex items-baseline justify-between">
            <span className="label">{group.label}</span>
            <span className="font-mono text-3xs text-faint">
              {group.weeks.flat().filter(Boolean).length} days
            </span>
          </div>
          <div className="grid grid-cols-7 gap-[5px]">
            {WEEKDAYS.map((day) => (
              <div key={day} className="text-3xs uppercase tracking-[0.1em] text-faint">
                {day}
              </div>
            ))}
            {group.weeks.flatMap((week, weekIndex) =>
              week.map((bucket, dayIndex) => {
                const key = `${group.key}-${weekIndex}-${dayIndex}`;
                if (!bucket) {
                  return <div key={key} aria-hidden className="h-9 rounded-control" />;
                }
                const value = metricValue(bucket, metric);
                const t = intensity(value, max);
                const isSelected = selected === bucket.start;
                const dayNumber = Number(bucket.start.slice(8, 10));

                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => onSelect(bucket)}
                    aria-pressed={isSelected}
                    aria-label={`${bucket.start}: ${value} ${metric}, ${bucket.state}`}
                    title={`${bucket.start} — ${value} ${metric} · ${bucket.state}`}
                    className={clsx(
                      "relative flex h-9 items-center justify-center rounded-control border text-3xs transition-colors duration-150",
                      bucket.state === "active"
                        ? "border-line/10 text-ink"
                        : bucket.state === "quiet"
                          ? "border-line/15 text-faint"
                          : "border-dashed border-line/20 text-faint/70",
                      isSelected ? "ring-1 ring-accent" : "",
                    )}
                    style={
                      bucket.state === "active"
                        ? {
                            backgroundColor: `rgba(239, 68, 68, ${0.18 + t * 0.72})`,
                            color: t > 0.55 ? "#0B0E16" : undefined,
                          }
                        : bucket.state === "quiet"
                          ? { backgroundColor: "rgba(148, 163, 184, 0.08)" }
                          : {
                              backgroundImage:
                                "repeating-linear-gradient(135deg, rgba(148,163,184,0.16) 0 1px, transparent 1px 6px)",
                            }
                    }
                  >
                    <span className="font-mono tabular-nums">{dayNumber}</span>
                  </button>
                );
              }),
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
