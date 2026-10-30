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
      <span className="inline-flex h-8 items-center gap-2 rounded-md border border-line/70 px-2.5 text-2xs text-faint">
        <StatusDot tone="neutral" />
        checking
      </span>
    );
  }

  if (isError || !data) {
    return (
      <span className="inline-flex h-8 items-center gap-2 rounded-md border border-danger/40 bg-danger/10 px-2.5 text-2xs text-danger">
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
      ? "border-ok/40 bg-ok/10 text-ok"
      : freshness.tone === "warn"
        ? "border-warn/40 bg-warn/10 text-warn"
        : freshness.tone === "danger"
          ? "border-danger/40 bg-danger/10 text-danger"
          : freshness.tone === "info"
            ? "border-geo/40 bg-geo/10 text-geo"
            : "border-line bg-raised/50 text-muted";

  return (
    <Popover
      label="Data freshness"
      widthClass="w-80"
      trigger={({ open, toggle, id }) => (
        <button
          type="button"
          id={id}
          onClick={toggle}
          aria-expanded={open}
          aria-haspopup="dialog"
          title={freshness.detail}
          className={`inline-flex h-8 items-center gap-2 rounded-md border px-2.5 text-2xs font-medium ${toneClass}`}
        >
          <StatusDot
            tone={freshness.tone === "ok" ? "ok" : freshness.tone === "warn" ? "warn" : "neutral"}
            pulse={freshness.tone === "ok"}
          />
          <span className="hidden sm:inline">{freshness.label}</span>
          <span className="sm:hidden">data</span>
        </button>
      )}
    >
      {() => (
        <div className="p-3.5">
          <div className="mb-2 flex items-center justify-between">
            <span className="label">Data freshness</span>
            <Badge tone="warn">not live</Badge>
          </div>
          <p className="text-xs leading-relaxed text-muted">{freshness.detail}</p>

          <dl className="mt-3 space-y-2 border-t border-line/70 pt-3 text-2xs">
            <div className="flex items-center justify-between gap-3">
              <dt className="inline-flex items-center gap-1.5 text-faint">
                <Satellite className="size-3" aria-hidden /> Sources registered
              </dt>
              <dd className="font-mono text-ink">{data.data.sources_registered}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="inline-flex items-center gap-1.5 text-faint">
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
              <dt className="inline-flex items-center gap-1.5 text-faint">
                <Database className="size-3" aria-hidden /> Database
              </dt>
              <dd className="inline-flex items-center gap-1.5 text-ink">
                <StatusDot tone={data.database.connected ? "ok" : "danger"} />
                {data.database.dialect}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-faint">Last ingestion</dt>
              <dd className="font-mono text-muted">
                {formatDateTimeUtc(data.data.last_ingested_at)}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-faint">API uptime</dt>
              <dd className="font-mono text-muted">{formatUptime(data.uptime_seconds)}</dd>
            </div>
          </dl>

          <p className="mt-3 flex items-start gap-1.5 border-t border-line/70 pt-2.5 text-2xs leading-relaxed text-faint">
            <AlertTriangle className="mt-0.5 size-3 shrink-0 text-warn" aria-hidden />
            A refreshing map is not a live feed. Freshness is derived from stored observations,
            not from page reloads.
          </p>
        </div>
      )}
    </Popover>
  );
}
