import { useEffect, useState } from "react";

import { useSystemStatus } from "@/lib/queries";
import { formatUtcClock } from "@/lib/time";
import { useUiStore } from "@/store/ui";
import { StatusDot } from "@/components/ui/StatusDot";

export function StatusBar() {
  const { data } = useSystemStatus();
  const dateRange = useUiStore((state) => state.dateRange);
  const [clock, setClock] = useState(() => formatUtcClock());

  useEffect(() => {
    const timer = window.setInterval(() => setClock(formatUtcClock()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <footer className="mt-auto border-t border-line/80 bg-sidebar/80 px-3 py-1.5 text-3xs text-faint sm:px-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="inline-flex items-center gap-1.5">
          <StatusDot tone={data ? (data.database.connected ? "ok" : "danger") : "neutral"} />
          {data ? `Phase ${data.phase} · ${data.phase_name}` : "Connecting to API"}
        </span>

        <span className="hidden items-center gap-1.5 sm:inline-flex">
          Period <span className="font-mono text-muted">{dateRange.start} → {dateRange.end}</span>
        </span>

        <span className="hidden items-center gap-1.5 md:inline-flex">
          Sources <span className="font-mono text-muted">{data?.data.sources_registered ?? "—"}</span>
        </span>

        <span className="hidden items-center gap-1.5 md:inline-flex">
          Database <span className="font-mono text-muted">{data?.database.dialect ?? "—"}</span>
        </span>

        <span className="ml-auto inline-flex items-center gap-1.5">
          <span className="font-mono text-muted">{clock}</span>
          <span className="hidden sm:inline">UTC</span>
        </span>

        <span className="hidden lg:inline">API v{data?.app_version ?? "—"}</span>
      </div>

      <p className="mt-1 border-t border-line/40 pt-1 leading-relaxed">
        NASA FIRMS thermal anomalies are detections, not confirmed wildfires: they may be false
        positives, may be agricultural or industrial heat, and can be obscured by cloud. Not for
        life-safety decisions.
      </p>
    </footer>
  );
}
