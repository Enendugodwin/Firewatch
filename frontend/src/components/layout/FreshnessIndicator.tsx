import { AlertTriangle, Database, Radio, Satellite } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Popover } from "@/components/ui/Popover";
import { StatusDot } from "@/components/ui/StatusDot";
import { describeFreshness } from "@/lib/freshness";
import { useSystemStatus } from "@/lib/queries";
import { formatDateTimeUtc, formatUptime } from "@/lib/time";

export function FreshnessIndicator() {
  const { data, isError, isLoading } = useSystemStatus();

  if (isLoading) {
    return (
      <span className="inline-flex h-8 items-center gap-2 rounded-full border border-line/10 px-[10px] text-2xs font-light text-faint">
        <StatusDot tone="neutral" />
        checking
      </span>
    );
  }

  if (isError || !data) {
    return (
      <span className="inline-flex h-8 items-center gap-2 rounded-full border border-danger/30 px-[10px] text-2xs font-medium text-danger">
        <StatusDot tone="danger" />
        API offline
      </span>
    );
  }

  const freshness = describeFreshness({
    freshness: data.data.freshness,
    freshnessReason: data.data.freshness_reason,
    lastObservationAt: data.data.last_observation_at,
  });

  const toneClass =
    freshness.tone === "ok"
      ? "border-accent/30 text-accent"
      : freshness.tone === "warn"
        ? "border-warn/30 text-warn"
        : freshness.tone === "danger"
          ? "border-danger/30 text-danger"
          : freshness.tone === "info"
            ? "border-azure/30 text-azure"
            : "border-line/10 text-muted";

  const dotTone =
    freshness.tone === "ok" ? "ok" : freshness.tone === "warn" ? "warn" : "neutral";

  return (
    <Popover
      label="Data freshness details"
      widthClass="w-[20rem]"
      trigger={({ open, toggle, id }) => (
        <button
          type="button"
          id={id}
          onClick={toggle}
          aria-expanded={open}
          aria-haspopup="dialog"
          aria-label="Data freshness"
          title={freshness.detail}
          className={`inline-flex h-8 items-center gap-2 rounded-full border bg-line/[0.02] px-[10px] text-2xs font-medium transition-colors duration-150 hover:bg-line/[0.05] ${toneClass}`}
        >
          <StatusDot tone={dotTone} pulse={freshness.tone === "ok"} />
          <span className="hidden sm:inline">{freshness.label}</span>
          <span className="sm:hidden">data</span>
        </button>
      )}
    >
      {() => (
        <div className="p-[16px]">
          <div className="mb-[10px] flex items-center justify-between">
            <span className="label">Data freshness</span>
            <Badge tone="warn">not live</Badge>
          </div>
          <p className="text-xs font-light leading-relaxed text-muted">{freshness.detail}</p>

          <dl className="mt-[12px] space-y-[8px] border-t border-line/[0.07] pt-[12px] text-2xs">
            <div className="flex items-center justify-between gap-3">
              <dt className="inline-flex items-center gap-1.5 font-light text-faint">
                <Satellite className="size-3" aria-hidden /> Sources registered
              </dt>
              <dd className="font-mono text-ink">{data.data.sources_registered}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="inline-flex items-center gap-1.5 font-light text-faint">
                <Radio className="size-3" aria-hidden /> FIRMS key
              </dt>
              <dd>
                {data.data.firms_configured ? (
                  <Badge tone="ok">configured</Badge>
                ) : (
                  <Badge tone="warn">missing</Badge>
                )}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="inline-flex items-center gap-1.5 font-light text-faint">
                <Database className="size-3" aria-hidden /> Database
              </dt>
              <dd className="inline-flex items-center gap-1.5 text-ink">
                <StatusDot tone={data.database.connected ? "ok" : "danger"} />
                {data.database.dialect}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="font-light text-faint">Last ingestion</dt>
              <dd className="font-mono text-muted">
                {formatDateTimeUtc(data.data.last_ingested_at)}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="font-light text-faint">API uptime</dt>
              <dd className="font-mono text-muted">{formatUptime(data.uptime_seconds)}</dd>
            </div>
          </dl>

          <p className="mt-[12px] flex items-start gap-1.5 border-t border-line/[0.07] pt-[10px] text-2xs font-light leading-relaxed text-faint">
            <AlertTriangle className="mt-[2px] size-3 shrink-0 text-warn" aria-hidden />A refreshing
            map is not a live feed. Freshness is derived from stored observations, not page reloads.
          </p>
        </div>
      )}
    </Popover>
  );
}
