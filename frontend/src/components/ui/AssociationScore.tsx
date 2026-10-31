import clsx from "clsx";

import type { MatchStatus } from "@/types/api";
import { formatScore } from "@/lib/format";

const STATUS_BAR: Record<MatchStatus, string> = {
  probable: "bg-accent/80",
  possible: "bg-azure/70",
  rejected: "bg-line/25",
};

/**
 * Association score visual. Deliberately labelled "association", never
 * "confidence" or "probability": the score does not mean the detections are the
 * same physical fire.
 */
export function AssociationScore({
  score,
  status,
  compact = false,
}: {
  score: number;
  status: MatchStatus;
  compact?: boolean;
}) {
  return (
    <div className={clsx("flex items-center gap-2", compact ? "w-28" : "w-40")}>
      <div className="h-[3px] flex-1 overflow-hidden rounded-full bg-line/10">
        <div
          className={clsx("h-full rounded-full", STATUS_BAR[status])}
          style={{ width: `${Math.max(2, Math.round(score * 100))}%` }}
        />
      </div>
      <span className="font-mono text-3xs tabular-nums text-muted">{formatScore(score)}</span>
    </div>
  );
}
