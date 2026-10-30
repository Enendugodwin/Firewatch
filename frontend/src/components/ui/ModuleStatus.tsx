import clsx from "clsx";
import type { ReactNode } from "react";

import type { ModuleStatus } from "@/types/api";

const STATUS_TONE: Record<ModuleStatus, string> = {
  ready: "border-accent/25 text-accent",
  in_progress: "border-azure/25 text-azure",
  scaffolded: "border-line/12 text-muted",
};

const STATUS_DOT: Record<ModuleStatus, string> = {
  ready: "bg-accent",
  in_progress: "bg-azure",
  scaffolded: "bg-line/35",
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
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-[3px] text-3xs font-medium uppercase tracking-[0.14em]",
        STATUS_TONE[status],
      )}
    >
      <span className={clsx("size-[5px] rounded-full", STATUS_DOT[status])} />
      {STATUS_LABEL[status]}
    </span>
  );
}

/** Delivery phase, stated quietly: phases are metadata, not activity. */
export function PhaseBadge({ phase }: { phase: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-line/[0.09] px-2 py-[3px] font-mono text-3xs uppercase tracking-[0.12em] text-faint">
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
    <div className="mb-6 border-b border-line/[0.07] pb-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          {eyebrow ? <div className="label mb-2">{eyebrow}</div> : null}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h1 className="font-display text-[34px] leading-[1.05] tracking-[-0.025em] text-ink sm:text-[40px]">
              {title}
            </h1>
            {status ? <ModuleStatusPill status={status} /> : null}
            {phase ? <PhaseBadge phase={phase} /> : null}
          </div>
          {description ? (
            <p className="mt-2 max-w-2xl text-[13px] font-light leading-[1.65] text-muted">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}
