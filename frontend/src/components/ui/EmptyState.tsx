import { Clock } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "./Badge";

/** Shown when a module exists but has no data yet — never faked numbers. */
export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-line/80 bg-canvas/40 px-6 py-10 text-center">
      <div className="mb-3 flex size-9 items-center justify-center rounded-full border border-line bg-raised/60 text-faint">
        {icon ?? <Clock className="size-4" aria-hidden />}
      </div>
      <h3 className="text-sm font-medium text-ink">{title}</h3>
      <p className="mt-1.5 max-w-md text-xs leading-relaxed text-muted">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function PendingDataNotice({ phase }: { phase: string }) {
  return (
    <EmptyState
      title="No observations available yet"
      description={
        <>
          This view is wired to the API, but nothing has been ingested. NASA FIRMS
          ingestion arrives in <span className="text-ink">{phase}</span>; until then the
          platform reports an empty state rather than sample data.
        </>
      }
      action={<Badge tone="warn">no data</Badge>}
    />
  );
}
