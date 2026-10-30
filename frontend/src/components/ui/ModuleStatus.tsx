import clsx from "clsx";
import type { ReactNode } from "react";

import type { ModuleStatus } from "@/types/api";

const STATUS_TONE: Record<ModuleStatus, string> = {
  ready: "border-ok/40 text-ok bg-ok/10",
  in_progress: "border-geo/40 text-geo bg-geo/10",
  scaffolded: "border-line text-muted bg-raised/60",
};

const STATUS_LABEL: Record<ModuleStatus, string> = {
  ready: "Operational",
  in_progress: "In progress",
  scaffolded: "Scaffolded",
};

export function ModuleStatusPill({ status }: { status: ModuleStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-3xs font-medium uppercase tracking-[0.12em]",
        STATUS_TONE[status],
      )}
    >
      <span
        className={clsx(
          "size-1.5 rounded-full",
          status === "ready" ? "bg-ok" : status === "in_progress" ? "bg-geo" : "bg-faint",
        )}
      />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function PhaseBadge({ phase }: { phase: string }) {
  return (
    <span className="inline-flex items-center rounded border border-fire-medium/30 bg-fire-medium/10 px-2 py-0.5 font-mono text-3xs uppercase tracking-[0.1em] text-fire-medium">
      {phase}
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  status,
  phase,
}: {
  eyebrow?: ReactNode;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  status?: ModuleStatus;
  phase?: string;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-4 border-b border-line/60 pb-4">
      <div className="min-w-0">
        {eyebrow ? <div className="label mb-1">{eyebrow}</div> : null}
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
          {status ? <ModuleStatusPill status={status} /> : null}
          {phase ? <PhaseBadge phase={phase} /> : null}
        </div>
        {description ? (
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}
