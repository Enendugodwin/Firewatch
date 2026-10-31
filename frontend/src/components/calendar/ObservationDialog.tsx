import { X } from "lucide-react";
import { useEffect, useId, useRef } from "react";

import { Badge } from "@/components/ui/Badge";
import { provenanceRows } from "@/lib/provenance";
import type { Observation } from "@/types/api";

/**
 * Detection provenance as a modal: inspecting a row must not move the page, so
 * the detail appears over the workspace and returns focus on close.
 */
export function ObservationDialog({
  observation,
  onClose,
}: {
  observation: Observation | null;
  onClose: () => void;
}) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const open = Boolean(observation);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      previouslyFocused.current?.focus();
    };
  }, [open, onClose]);

  if (!observation) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-[#05070F]/70 p-4 backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="mx-auto my-auto w-full max-w-xl rounded-card border border-line/[0.12] bg-panel shadow-lift"
      >
        <div className="flex items-start justify-between gap-3 border-b border-line/[0.07] px-[18px] py-[13px]">
          <div className="min-w-0">
            <div className="label" id={titleId}>
              Detection detail
            </div>
            <div className="mt-[4px] flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-ink">
                {observation.latitude.toFixed(4)}, {observation.longitude.toFixed(4)}
              </span>
              <Badge tone={observation.sensor === "MODIS" ? "info" : "ok"}>
                {observation.sensor}
              </Badge>
              {observation.is_synthetic ? <Badge tone="warn">synthetic</Badge> : null}
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close detection detail"
            className="rounded-full p-1 text-faint transition-colors duration-150 hover:bg-line/[0.06] hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>

        <div className="max-h-[min(70vh,32rem)] overflow-y-auto px-[18px] py-[14px]">
          <dl className="divide-y divide-line/[0.06]">
            {provenanceRows(observation).map((row) => (
              <div key={row.label} className="flex items-start justify-between gap-4 py-[7px]">
                <dt className="shrink-0 text-2xs font-light text-faint">{row.label}</dt>
                <dd className="min-w-0 break-all text-right font-mono text-3xs text-muted">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>

          {observation.is_synthetic ? (
            <p className="mt-[10px] rounded-control border border-warn/25 bg-warn/[0.06] px-2 py-[6px] text-3xs font-light text-warn">
              Synthetic fixture row — not a NASA observation.
            </p>
          ) : null}

          <p className="mt-[10px] border-t border-line/[0.07] pt-[9px] text-3xs font-light leading-relaxed text-faint">
            A detection is a thermal anomaly, not a confirmed fire. Provenance: NASA FIRMS{" "}
            {observation.source_product}.
          </p>
        </div>
      </div>
    </div>
  );
}
