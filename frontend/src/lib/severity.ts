/**
 * Anomaly severity helpers shared by the calendar grid, the bars and the
 * intelligence panel. A day without a ranked severity is simply not marked:
 * `normal`, `below_baseline` and `unobserved` never get an alert marker.
 */

export const RANKED_SEVERITIES = ["moderate", "high", "critical"] as const;
export type RankedSeverity = (typeof RANKED_SEVERITIES)[number];

const RANK: Record<string, number> = {
  normal: 0,
  unobserved: 0,
  unknown_scale: 0,
  below_baseline: 0,
  moderate: 1,
  high: 2,
  critical: 3,
};

export type SeverityByDay = Record<string, string | undefined>;

export function isRankedSeverity(
  severity: string | null | undefined,
): severity is RankedSeverity {
  return Boolean(severity && RANKED_SEVERITIES.includes(severity as RankedSeverity));
}

export function severityRank(severity: string | null | undefined): number {
  return severity ? (RANK[severity] ?? 0) : 0;
}

export function maxSeverity(
  ...severities: Array<string | null | undefined>
): RankedSeverity | null {
  let best: RankedSeverity | null = null;
  for (const severity of severities) {
    if (!isRankedSeverity(severity)) continue;
    if (best === null || severityRank(severity) > severityRank(best)) {
      best = severity as RankedSeverity;
    }
  }
  return best;
}

/** Strongest anomaly inside an inclusive ISO date range; null when none. */
export function maxSeverityInRange(
  severityByDay: SeverityByDay | undefined,
  start: string,
  end: string,
): RankedSeverity | null {
  if (!severityByDay) return null;
  let best: RankedSeverity | null = null;
  const cursor = new Date(`${start}T00:00:00Z`);
  const last = new Date(`${end}T00:00:00Z`);
  // Ranges are bounded by the calendar (<= 6 years), so a day walk is cheap and
  // avoids timezone arithmetic bugs.
  while (cursor <= last) {
    const key = cursor.toISOString().slice(0, 10);
    const candidate = severityByDay[key];
    if (isRankedSeverity(candidate)) {
      if (best === null || severityRank(candidate) > severityRank(best)) {
        best = candidate as RankedSeverity;
      }
    }
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return best;
}

export function severityDotClass(severity: RankedSeverity | null): string {
  if (severity === "critical") return "bg-[#f87171]";
  if (severity === "high") return "bg-[#fbbf24]";
  return "bg-[#7dd3fc]";
}

export function severityLabel(severity: string): string {
  if (severity === "below_baseline") return "below baseline";
  if (severity === "unknown_scale") return "unrankable";
  return severity;
}
