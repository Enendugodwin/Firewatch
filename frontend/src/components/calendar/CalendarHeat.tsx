import clsx from "clsx";

import type { CalendarBucket, CalendarMetric } from "@/lib/calendarApi";
import { intensity, metricValue } from "@/lib/calendarApi";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

interface MonthGroup {
  key: string;
  label: string;
  year: number;
  month: number;
  weeks: Array<Array<CalendarBucket | null>>;
  detections: number;
}

function monthLabel(date: Date): string {
  return `${MONTH_NAMES[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
}

/**
 * Group day buckets into Monday-first weeks, one group per month, padded to a
 * full calendar grid. A month is laid out the way a wall calendar is: leading
 * blanks before the 1st, whole weeks after it.
 */
export function groupIntoMonths(buckets: CalendarBucket[]): MonthGroup[] {
  const groups = new Map<string, MonthGroup>();
  for (const bucket of buckets) {
    const date = new Date(`${bucket.start}T00:00:00Z`);
    const key = bucket.start.slice(0, 7);
    let group = groups.get(key);
    if (!group) {
      group = {
        key,
        label: monthLabel(date),
        year: date.getUTCFullYear(),
        month: date.getUTCMonth(),
        weeks: [Array.from({ length: 7 }, () => null)],
        detections: 0,
      };
      groups.set(key, group);
    }
    group.detections += bucket.detections;

    const weekday = (date.getUTCDay() + 6) % 7;
    if (weekday === 0 && group.weeks[0]!.some(Boolean)) {
      group.weeks.push(Array.from({ length: 7 }, () => null));
    }
    let week = group.weeks[group.weeks.length - 1]!;
    if (week[weekday] !== null) {
      week = Array.from({ length: 7 }, () => null);
      group.weeks.push(week);
    }
    week[weekday] = bucket;
  }

  // Drop the initial row when the month starts on a Monday, and pad the last
  // week so every month renders the same six-row shape.
  for (const group of groups.values()) {
    while (group.weeks.length && group.weeks[group.weeks.length - 1]!.every((cell) => cell === null)) {
      group.weeks.pop();
    }
    while (group.weeks.length < 5) {
      group.weeks.push(Array.from({ length: 7 }, () => null));
    }
  }

  return [...groups.values()];
}

function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

export function CalendarHeat({
  buckets,
  metric,
  selected,
  onSelect,
  granularity = "day",
}: {
  buckets: CalendarBucket[];
  metric: CalendarMetric;
  selected: string | null;
  onSelect: (bucket: CalendarBucket) => void;
  granularity?: string;
}) {
  const groups = groupIntoMonths(buckets);
  const max = Math.max(0, ...buckets.map((bucket) => metricValue(bucket, metric)));
  const today = todayUtc();

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {groups.map((group) => (
        <section
          key={group.key}
          aria-label={group.label}
          className="rounded-card border border-line/[0.08] bg-line/[0.015] p-3"
        >
          <header className="mb-2 flex items-baseline justify-between gap-2 px-1">
            <h3 className="text-[13px] font-medium tracking-[0.01em] text-ink">{group.label}</h3>
            <span className="font-mono text-3xs text-faint">
              {group.detections > 0 ? `${group.detections.toLocaleString("en-US")} detections` : "no activity"}
            </span>
          </header>

          <div className="grid grid-cols-7 gap-1">
            {WEEKDAYS.map((day) => (
              <div
                key={day}
                className="pb-1 text-center text-3xs uppercase tracking-[0.1em] text-faint"
              >
                {day}
              </div>
            ))}

            {group.weeks.flatMap((week, weekIndex) =>
              week.map((bucket, dayIndex) => {
                const key = `${group.key}-${weekIndex}-${dayIndex}`;
                if (!bucket) {
                  return (
                    <div
                      key={key}
                      aria-hidden
                      className="aspect-square rounded-control border border-dashed border-line/[0.05]"
                    />
                  );
                }

                const value = metricValue(bucket, metric);
                const t = intensity(value, max);
                const isSelected = selected === bucket.start;
                const isToday = bucket.start === today;
                const dayNumber = Number(bucket.start.slice(8, 10));
                const weekday = new Date(`${bucket.start}T00:00:00Z`).getUTCDay();
                const isWeekend = weekday === 0 || weekday === 6;

                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => onSelect(bucket)}
                    aria-pressed={isSelected}
                    aria-label={`${bucket.start}: ${value} ${metric}, ${bucket.state}`}
                    title={`${bucket.start} — ${value} ${metric} · ${bucket.state}`}
                    className={clsx(
                      "group relative aspect-square rounded-control border text-left transition-all duration-150",
                      bucket.state === "active"
                        ? "border-line/10 hover:border-line/30"
                        : bucket.state === "quiet"
                          ? "border-line/[0.12] hover:border-line/25"
                          : "border-dashed border-line/20 hover:border-line/35",
                      isSelected && "ring-2 ring-accent ring-offset-1 ring-offset-panel",
                      isToday && !isSelected && "ring-1 ring-azure/60",
                    )}
                    style={
                      bucket.state === "active"
                        ? {
                            backgroundColor: `rgba(239, 68, 68, ${0.16 + t * 0.74})`,
                            color: t > 0.55 ? "#0B0E16" : undefined,
                          }
                        : bucket.state === "quiet"
                          ? { backgroundColor: "rgba(148, 163, 184, 0.07)" }
                          : {
                              backgroundImage:
                                "repeating-linear-gradient(135deg, rgba(148,163,184,0.16) 0 1px, transparent 1px 6px)",
                            }
                    }
                  >
                    <span
                      className={clsx(
                        "absolute left-[5px] top-[3px] font-mono text-[11px] tabular-nums",
                        isWeekend && bucket.state !== "active" ? "text-faint" : "",
                      )}
                    >
                      {dayNumber}
                    </span>
                    {value > 0 ? (
                      <span className="absolute bottom-[3px] right-[4px] font-mono text-[9px] tabular-nums opacity-80">
                        {value >= 10000
                          ? `${Math.round(value / 1000)}k`
                          : value >= 1000
                            ? `${(value / 1000).toFixed(1)}k`
                            : value}
                      </span>
                    ) : null}
                  </button>
                );
              }),
            )}
          </div>
        </section>
      ))}

      {granularity === "day" ? (
        <p className="lg:col-span-2 text-3xs font-light leading-relaxed text-faint">
          Each square is one UTC day. Shading follows {metric === "frp" ? "FRP" : metric.replace("_", " ")};
          hatched days have no source availability and are never counted as zero. Today is outlined in
          blue.
        </p>
      ) : null}
    </div>
  );
}
