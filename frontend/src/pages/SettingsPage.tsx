import { AlertTriangle, Check, KeyRound, X } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel, StatTile } from "@/components/ui/Panel";
import { StatusDot } from "@/components/ui/StatusDot";
import { useSources, useSystemStatus } from "@/lib/queries";
import { formatDateTimeUtc, formatUptime } from "@/lib/time";

function CapabilityRow({ label, enabled, note }: { label: string; enabled: boolean; note: string }) {
  return (
    <li className="flex items-start gap-2.5 px-4 py-2.5">
      {enabled ? (
        <Check className="mt-0.5 size-3.5 shrink-0 text-ok" aria-hidden />
      ) : (
        <X className="mt-0.5 size-3.5 shrink-0 text-faint" aria-hidden />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-ink">{label}</span>
          <Badge tone={enabled ? "ok" : "neutral"}>{enabled ? "available" : "not built"}</Badge>
        </div>
        <p className="mt-0.5 text-2xs leading-relaxed text-faint">{note}</p>
      </div>
    </li>
  );
}

export function SettingsPage() {
  const { data: status, isError } = useSystemStatus();
  const { data: sources } = useSources();

  const config = [
    {
      name: "FIRMS_MAP_KEY",
      purpose: "Authorises NASA FIRMS retrieval. Backend-only, never exposed to the browser.",
      ok: status?.data.firms_configured ?? false,
      env: "FIRMS_MAP_KEY=your_nasa_firms_map_key",
    },
    {
      name: "DATABASE_URL",
      purpose: "Primary store. PostgreSQL with PostGIS in every real deployment.",
      ok: status?.database.connected ?? false,
      env: "postgresql+psycopg://user:password@db:5432/firewatch",
    },
    {
      name: "REDIS_URL",
      purpose: "Cache and job coordination for ingestion and report workers.",
      ok: false,
      env: "redis://redis:6379/0",
    },
    {
      name: "AI_PROVIDER / AI_API_KEY / AI_MODEL",
      purpose: "Optional. Statistical intelligence works without an LLM.",
      ok: status?.capabilities.ai_assistant ?? false,
      env: "AI_PROVIDER= AI_API_KEY= AI_MODEL=",
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="System"
        title="Settings & Administration"
        description="Configuration, data-source registry and capability truth for this deployment."
        status="in_progress"
        phase="Phase 1"
      />

      {isError ? (
        <div className="mb-4 flex items-start gap-2.5 rounded-md border border-danger/40 bg-danger/10 px-3.5 py-3">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
          <p className="text-xs text-danger">
            The API is unreachable, so configuration state cannot be verified.
          </p>
        </div>
      ) : null}

      <div className="mb-4 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Environment"
          value={status?.environment ?? "—"}
          hint={status ? `${status.app_name} v${status.app_version}` : undefined}
        />
        <StatTile
          label="Phase"
          value={status ? `${status.phase} · ${status.phase_name}` : "—"}
          hint="Current delivery milestone"
          tone="info"
        />
        <StatTile
          label="Database"
          value={status?.database.dialect ?? "—"}
          hint={
            status?.database.connected
              ? `${status.database.latency_ms ?? "?"} ms probe · PostGIS ${
                  status.database.postgis === null
                    ? "n/a"
                    : status.database.postgis
                      ? "enabled"
                      : "missing"
                }`
              : (status?.database.error ?? "Not reachable")
          }
          tone={status?.database.connected ? "ok" : "warn"}
        />
        <StatTile
          label="API uptime"
          value={status ? formatUptime(status.uptime_seconds) : "—"}
          hint={status ? `Server time ${formatDateTimeUtc(status.server_time)}` : undefined}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Panel
            title="Data sources"
            subtitle="The only products this platform supports in the first release."
            bodyClassName="p-0"
          >
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-line/70 text-3xs uppercase tracking-[0.1em] text-faint">
                    <th scope="col" className="px-4 py-2 font-medium">Source</th>
                    <th scope="col" className="px-3 py-2 font-medium">Sensor</th>
                    <th scope="col" className="px-3 py-2 font-medium">Satellite</th>
                    <th scope="col" className="px-3 py-2 font-medium">Level</th>
                    <th scope="col" className="px-4 py-2 text-right font-medium">State</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/50">
                  {(sources ?? []).map((source) => (
                    <tr key={source.code} className="hover:bg-raised/40">
                      <td className="px-4 py-2 font-mono text-2xs text-ink">{source.code}</td>
                      <td className="px-3 py-2 text-muted">{source.sensor}</td>
                      <td className="px-3 py-2 text-muted">{source.satellite}</td>
                      <td className="px-3 py-2">
                        <Badge tone={source.processing_level === "SP" ? "info" : "neutral"}>
                          {source.processing_level}
                        </Badge>
                      </td>
                      <td className="px-4 py-2 text-right">
                        <span className="inline-flex items-center gap-1.5 text-2xs text-muted">
                          <StatusDot tone="neutral" />
                          not ingested
                        </span>
                      </td>
                    </tr>
                  ))}
                  {!sources ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-center text-xs text-faint">
                        Loading source registry…
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <p className="border-t border-line/60 px-4 py-2.5 text-2xs leading-relaxed text-faint">
              <span className="text-muted">SP</span> = standard processing (historical analysis) ·{" "}
              <span className="text-muted">NRT</span> = near-real-time (operational monitoring).
              Processing versions are never combined silently.
            </p>
          </Panel>

          <Panel
            title="Required configuration"
            subtitle="Environment variables read by the API at startup."
            bodyClassName="p-0"
          >
            <ul className="divide-y divide-line/60">
              {config.map((item) => (
                <li key={item.name} className="px-4 py-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 font-mono text-2xs text-ink">
                      <KeyRound className="size-3 text-faint" aria-hidden />
                      {item.name}
                    </span>
                    {item.ok ? (
                      <Badge tone="ok">configured</Badge>
                    ) : (
                      <Badge tone="warn">missing</Badge>
                    )}
                  </div>
                  <p className="mt-1 text-2xs leading-relaxed text-muted">{item.purpose}</p>
                  <code className="mt-1.5 block overflow-x-auto rounded border border-line/60 bg-canvas px-2 py-1 font-mono text-3xs text-faint">
                    {item.env}
                  </code>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel
            title="Capabilities"
            subtitle="Reported by /api/v1/system/status — not marketing copy."
            bodyClassName="p-0"
          >
            <ul className="divide-y divide-line/60">
              <CapabilityRow
                label="Authentication & RBAC"
                enabled={status?.capabilities.authentication ?? false}
                note="Argon2id, roles and sessions arrive in the security phase."
              />
              <CapabilityRow
                label="Rate limiting"
                enabled={status?.capabilities.rate_limiting ?? false}
                note="Per-client limits for public endpoints."
              />
              <CapabilityRow
                label="NASA ingestion"
                enabled={status?.capabilities.ingestion ?? false}
                note="Tiled, resumable FIRMS retrieval (Phase 2)."
              />
              <CapabilityRow
                label="Spatial queries"
                enabled={status?.capabilities.spatial ?? false}
                note="Requires PostgreSQL with PostGIS; SQLite reports false."
              />
              <CapabilityRow
                label="Reports & exports"
                enabled={status?.capabilities.reports ?? false}
                note="PDF, CSV, GeoJSON and JSON with methodology."
              />
              <CapabilityRow
                label="AI assistant"
                enabled={status?.capabilities.ai_assistant ?? false}
                note="Tool-calling over approved functions only."
              />
            </ul>
          </Panel>

          <Panel title="Deployment notes">
            <ul className="space-y-2 text-2xs leading-relaxed text-muted">
              <li>
                <span className="text-ink">Secrets stay on the backend.</span> The FIRMS key and
                database credentials are never sent to the browser or embedded in the frontend
                bundle.
              </li>
              <li>
                <span className="text-ink">No auth yet.</span> The console is open; bind it to
                localhost or a trusted network until the security phase lands.
              </li>
              <li>
                <span className="text-ink">PostGIS required.</span> SQLite is only for local
                development and the test suite; spatial capability reports false there.
              </li>
            </ul>
          </Panel>

          <div className="flex items-start gap-2.5 rounded-panel border border-warn/30 bg-warn/5 px-3.5 py-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden />
            <p className="text-2xs leading-relaxed text-muted">
              <span className="text-ink">Evidence standard.</span> Every analytical value must
              reconcile with stored observations and keep NASA attribution visible. Where data is
              absent, FIREWATCH X shows an empty state.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
