import { useEffect, useState } from "react";

import { useSystemStatus } from "@/lib/queries";
import { formatUtcClock } from "@/lib/time";
import { useUiStore } from "@/store/ui";
import { StatusDot } from "@/components/ui/StatusDot";

const item = "inline-flex items-center gap-[6px]";

export function StatusBar() {
  const { data } = useSystemStatus();
  const dateRange = useUiStore((state) => state.dateRange);
  const [clock, setClock] = useState(() => formatUtcClock());

  useEffect(() => {
    const timer = window.setInterval(() => setClock(formatUtcClock()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <footer className="relative z-10 border-t border-line/[0.07] px-3 py-[7px] text-3xs font-light text-faint sm:px-[22px]">
      <div className="flex flex-wrap items-center gap-x-[18px] gap-y-1">
        <span className={item}>
          <StatusDot tone={data ? (data.database.connected ? "ok" : "danger") : "neutral"} />
          {data ? `Phase ${data.phase} · ${data.phase_name}` : "Connecting to API"}
        </span>

        <span className={`${item} hidden sm:inline-flex`}>
          Period
          <span className="font-mono text-muted">
            {dateRange.start} → {dateRange.end}
          </span>
        </span>

        <span className={`${item} hidden md:inline-flex`}>
          Sources <span className="font-mono text-muted">{data?.data.sources_registered ?? "—"}</span>
        </span>

        <span className={`${item} hidden md:inline-flex`}>
          Database <span className="font-mono text-muted">{data?.database.dialect ?? "—"}</span>
        </span>

        <span className={`${item} ml-auto`}>
          <span className="font-mono text-muted">{clock}</span>
          <span className="hidden sm:inline">UTC</span>
        </span>

        <span className="hidden lg:inline">API v{data?.app_version ?? "—"}</span>
      </div>

      <p className="mt-[5px] border-t border-line/[0.05] pt-[5px] leading-relaxed">
        NASA FIRMS thermal anomalies are detections, not confirmed wildfires: they may be false
        positives, may be agricultural or industrial heat, and can be obscured by cloud. Not for
        life-safety decisions.
      </p>
    </footer>
  );
}
