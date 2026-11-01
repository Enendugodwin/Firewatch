import { AlertTriangle, X } from "lucide-react";

import { ObservationDialog } from "@/components/calendar/ObservationDialog";
import { Badge } from "@/components/ui/Badge";
import { LoadingBlock } from "@/components/ui/LoadingCue";
import { DataRow } from "@/components/ui/Panel";
import type { CalendarDrilldown } from "@/lib/calendarApi";
import { formatCount, formatFrp } from "@/lib/format";

/**
 * Drill-down for one calendar bucket. Lists the detections that produced the
 * bucket's counts, with the full stored provenance for the selected row.
 */
function dayCount(bucket: CalendarDrilldown["bucket"]): number {
  const start = Date.parse(`${bucket.start}T00:00:00Z`);
  const end = Date.parse(`${bucket.end}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(end)) return 0;
  return Math.round((end - start) / 86_400_000) + 1;
}

export function BucketPanel({
  bucketStart,
  data,
  loading,
  error,
  selectedId,
  onSelect,
  onClose,
}: {
  bucketStart: string;
  data: CalendarDrilldown | undefined;
  loading: boolean;
  error: string | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onClose: () => void;
}) {
  const bucket = data?.bucket;
  const observation = data?.items.find((item) => item.id === selectedId) ?? null;

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-card border border-line/[0.1] bg-panel/95 shadow-lift backdrop-blur-glass">
      <div className="flex items-start justify-between gap-3 border-b border-line/[0.07] px-[14px] py-[11px]">
        <div className="min-w-0">
          <div className="label">Bucket detail</div>
          <div className="mt-[3px] flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-ink">{bucketStart}</span>
            {bucket ? (
              <Badge
                tone={
                  bucket.state === "active" ? "ok" : bucket.state === "quiet" ? "neutral" : "warn"
                }
              >
                {bucket.state}
              </Badge>
            ) : null}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close bucket detail"
          className="rounded-full p-1 text-faint transition-colors duration-150 hover:bg-line/[0.06] hover:text-ink"
        >
          <X className="size-3.5" aria-hidden />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-[14px] py-[10px]">
        {loading ? (
          <LoadingBlock label="Loading detections for this bucket…" lines={3} />
        ) : null}
        {error ? (
          <div className="flex items-start gap-2 text-2xs text-danger">
            <AlertTriangle className="mt-[1px] size-3 shrink-0" aria-hidden />
            {error}
          </div>
        ) : null}

        {bucket ? (
          <div className="mb-[10px]">
            <DataRow label="Detections">{formatCount(bucket.detections)}</DataRow>
            <DataRow label="MODIS / VIIRS">
              {formatCount(bucket.modis)} / {formatCount(bucket.viirs)}
            </DataRow>
            <DataRow label="FRP total">{formatFrp(bucket.frp_sum_mw)}</DataRow>
            <DataRow label="FRP max">{formatFrp(bucket.frp_max_mw)}</DataRow>
            <DataRow label="High confidence">{formatCount(bucket.high_confidence)}</DataRow>
            <DataRow label="Days in bucket">{dayCount(bucket)}</DataRow>
            <DataRow label="Coverage">
              {bucket.coverage.observed} observed · {bucket.coverage.missing} missing ·{" "}
              {bucket.coverage.unknown} unknown
            </DataRow>
          </div>
        ) : null}

        {bucket && bucket.state !== "active" ? (
          <p className="mb-[10px] rounded-control border border-line/[0.1] bg-line/[0.03] px-2 py-[6px] text-2xs font-light leading-relaxed text-muted">
            {bucket.state === "quiet"
              ? "A source observed this period and reported no detections. This is a real zero."
              : "No availability was recorded for this period, so it cannot be read as zero activity."}
          </p>
        ) : null}

        {data && data.items.length > 0 ? (
          <ul className="space-y-[3px]">
            {data.items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => onSelect(item.id)}
                  aria-pressed={item.id === selectedId}
                  aria-haspopup="dialog"
                  className={`flex w-full items-center gap-2 rounded-control border px-2 py-[5px] text-left text-3xs transition-colors duration-150 ${
                    item.id === selectedId
                      ? "border-accent/35 bg-line/[0.05]"
                      : "border-line/[0.06] hover:border-line/20"
                  }`}
                >
                  <span className="font-mono text-faint">
                    {item.acquired_at.slice(11, 16)}Z
                  </span>
                  <span
                    className="size-1.5 shrink-0 rounded-full"
                    style={{
                      backgroundColor: item.sensor === "MODIS" ? "#1D4ED8" : "#15803D",
                    }}
                    aria-hidden
                  />
                  <span className="w-11 shrink-0 text-muted">{item.sensor}</span>
                  <span className="flex-1 truncate text-faint">
                    {item.confidence_category ?? "n/a"}
                  </span>
                  <span className="font-mono text-muted">{formatFrp(item.frp_mw)}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {data && data.total > data.items.length ? (
          <p className="mt-[8px] text-3xs font-light text-faint">
            Showing the most recent {data.items.length} of {formatCount(data.total)} detections.
          </p>
        ) : null}

      </div>

      <ObservationDialog observation={observation} onClose={() => onSelect(null)} />
    </div>
  );
}
