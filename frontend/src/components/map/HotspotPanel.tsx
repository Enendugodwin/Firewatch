import { AlertTriangle, X } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import type { Observation } from "@/types/api";
import { provenanceRows } from "./fireLayers";

export function HotspotPanel({
  observation,
  loading,
  error,
  onClose,
}: {
  observation: Observation | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  if (!observation && !loading && !error) return null;

  const suspectedNonFire =
    observation?.quality_flags &&
    (observation.quality_flags as Record<string, unknown>).suspected_non_fire === true;

  return (
    <div className="pointer-events-auto max-h-full w-full overflow-y-auto rounded-card border border-line/[0.1] bg-panel/95 shadow-lift backdrop-blur-glass sm:w-[21rem]">
      <div className="flex items-start justify-between gap-3 border-b border-line/[0.07] px-[14px] py-[11px]">
        <div className="min-w-0">
          <div className="label">Detection detail</div>
          <div className="mt-[3px] flex items-center gap-2">
            {observation ? (
              <>
                <span className="font-mono text-xs text-ink">
                  {observation.latitude.toFixed(4)}, {observation.longitude.toFixed(4)}
                </span>
                <Badge tone={observation.sensor === "MODIS" ? "info" : "ok"}>
                  {observation.sensor}
                </Badge>
              </>
            ) : (
              <span className="text-xs text-muted">{loading ? "Loading…" : "Unavailable"}</span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close detection detail"
          className="rounded-full p-1 text-faint transition-colors duration-150 hover:bg-line/[0.06] hover:text-ink"
        >
          <X className="size-3.5" aria-hidden />
        </button>
      </div>

      {error ? (
        <div className="flex items-start gap-2 px-[14px] py-[12px] text-2xs font-light text-danger">
          <AlertTriangle className="mt-[1px] size-3 shrink-0" aria-hidden />
          {error}
        </div>
      ) : null}

      {observation ? (
        <div className="px-[14px] py-[10px]">
          {observation.is_synthetic ? (
            <div className="mb-[10px] rounded-control border border-warn/25 bg-warn/[0.06] px-2 py-[6px] text-2xs font-light text-warn">
              Synthetic fixture row — not a NASA observation.
            </div>
          ) : null}

          {suspectedNonFire ? (
            <div className="mb-[10px] rounded-control border border-warn/25 bg-warn/[0.06] px-2 py-[6px] text-2xs font-light text-muted">
              <span className="text-warn">Thermal anomaly, probably not a fire.</span> FIRMS type
              marks a volcano, static land or offshore source.
            </div>
          ) : null}

          <dl className="divide-y divide-line/[0.06]">
            {provenanceRows(observation).map((row) => (
              <div key={row.label} className="flex items-start justify-between gap-3 py-[6px]">
                <dt className="shrink-0 text-2xs font-light text-faint">{row.label}</dt>
                <dd className="min-w-0 break-all text-right font-mono text-3xs text-muted">{row.value}</dd>
              </div>
            ))}
          </dl>

          <details className="mt-[10px] border-t border-line/[0.07] pt-[9px]">
            <summary className="cursor-pointer text-3xs uppercase tracking-[0.12em] text-faint">
              Original source record
            </summary>
            <pre className="mt-[6px] max-h-40 overflow-auto rounded-control border border-line/[0.08] bg-canvas/70 p-[8px] font-mono text-3xs leading-relaxed text-muted">
              {JSON.stringify(observation.quality_flags, null, 2)}
            </pre>
          </details>

          <p className="mt-[10px] border-t border-line/[0.07] pt-[9px] text-3xs font-light leading-relaxed text-faint">
            A detection is a thermal anomaly, not a confirmed fire. Provenance: NASA FIRMS{" "}
            {observation.source_product}.
          </p>
        </div>
      ) : null}
    </div>
  );
}
