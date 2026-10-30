import { formatDistanceStrict } from "./time";

/** Human-readable freshness for the header indicator. */
export interface FreshnessView {
  label: string;
  tone: "ok" | "info" | "warn" | "danger" | "neutral";
  detail: string;
}

export function describeFreshness(input: {
  freshness: string;
  freshnessReason: string;
  lastObservationAt: string | null;
  now?: Date;
}): FreshnessView {
  const { freshness, freshnessReason, lastObservationAt } = input;

  if (freshness === "no_data") {
    return {
      label: "No NASA data",
      tone: "warn",
      detail: freshnessReason,
    };
  }

  if (lastObservationAt) {
    const age = formatDistanceStrict(lastObservationAt, input.now ?? new Date());
    if (freshness === "current") {
      return { label: `Current · ${age} ago`, tone: "ok", detail: freshnessReason };
    }
    if (freshness === "delayed") {
      return { label: `Delayed · ${age} ago`, tone: "warn", detail: freshnessReason };
    }
    if (freshness === "stale") {
      return { label: `Stale · ${age} ago`, tone: "danger", detail: freshnessReason };
    }
    return { label: `Unknown · ${age} ago`, tone: "neutral", detail: freshnessReason };
  }

  return { label: "Unknown", tone: "neutral", detail: freshnessReason };
}
