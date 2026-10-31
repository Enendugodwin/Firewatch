import { useState } from "react";
import { AlertTriangle, Check, KeyRound, Layers, Play, X } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel, StatTile } from "@/components/ui/Panel";
import { StatusDot } from "@/components/ui/StatusDot";
import { ApiError } from "@/lib/api";
import {
  useIngestionRuns,
  useModules,
  useRunAllIngestion,
  useRunIngestion,
  useSourceHealth,
  useSources,
  useSystemStatus,
} from "@/lib/queries";
import { formatCount } from "@/lib/format";
import { addDays, formatDateTimeUtc, formatUtcDate, formatUptime } from "@/lib/time";

function CapabilityRow({ label, enabled, note }: { label: string; enabled: boolean; note: string }) {
  return (
    <li className="flex items-start gap-[10px] border-b border-line/[0.06] px-[22px] py-[11px] last:border-0">
      {enabled ? (
        <Check className="mt-[2px] size-3.5 shrink-0 text-accent" aria-hidden />
      ) : (
        <X className="mt-[2px] size-3.5 shrink-0 text-faint" aria-hidden />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-ink">{label}</span>
          <Badge tone={enabled ? "ok" : "neutral"}>{enabled ? "available" : "not built"}</Badge>
        </div>
        <p className="mt-[3px] text-2xs font-light leading-relaxed text-faint">{note}</p>
      </div>
    </li>
  );
}

function IngestionConsole() {
  const { data: status } = useSystemStatus();
  const { data: sources } = useSources();
  const runIngestion = useRunIngestion();
  const runAll = useRunAllIngestion();

  const today = formatUtcDate();
  const [sourceCode, setSourceCode] = useState("VIIRS_SNPP_NRT");
  const [startDate, setStartDate] = useState(formatUtcDate(addDays(new Date(), -1)));
  const [endDate, setEndDate] = useState(today);

  const configured = status?.data.firms_configured ?? false;
  const busy = runIngestion.isPending || runAll.isPending;
  const error = runIngestion.error ?? runAll.error;

  return (
    <Panel
      title="Ingestion console"
      subtitle="Retrieve a bounded window. Long backfills belong in scripts, not request handlers."
      actions={
        configured ? (
          <Badge tone="ok">key configured</Badge>
        ) : (
          <Badge tone="warn">key missing</Badge>
        )
      }
    >
      <div className="grid gap-[10px] sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
        <label className="text-2xs font-light text-faint">
          Source
          <select
            value={sourceCode}
            onChange={(event) => setSourceCode(event.target.value)}
            className="mt-[5px] w-full rounded-control border border-line/10 bg-canvas/60 px-2 py-[7px] font-mono text-2xs text-ink"
          >
            {(sources ?? []).map((source) => (
              <option key={source.code} value={source.code}>
                {source.code}
              </option>
            ))}
          </select>
        </label>
        <label className="text-2xs font-light text-faint">
          Start (UTC)
          <input
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            className="mt-[5px] w-full rounded-control border border-line/10 bg-canvas/60 px-2 py-[7px] font-mono text-2xs text-ink"
          />
        </label>
        <label className="text-2xs font-light text-faint">
          End (UTC)
          <input
            type="date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            className="mt-[5px] w-full rounded-control border border-line/10 bg-canvas/60 px-2 py-[7px] font-mono text-2xs text-ink"
          />
        </label>
        <div className="flex flex-wrap items-end gap-2">
          <Button
            variant="primary"
            disabled={busy || !configured}
            title={configured ? "Retrieve this window" : "Set FIRMS_MAP_KEY first"}
            onClick={() =>
              runIngestion.mutate({
                source_code: sourceCode,
                start_date: startDate,
                end_date: endDate,
              })
            }
          >
            <Play className="size-3" aria-hidden />
            {runIngestion.isPending ? "Retrieving…" : "Run window"}
          </Button>
          <Button
            variant="secondary"
            disabled={busy || !configured}
            title={
              configured
                ? "Run this window for every registered product"
                : "Set FIRMS_MAP_KEY first"
            }
            onClick={() =>
              runAll.mutate({
                start_date: startDate,
                end_date: endDate,
              })
            }
          >
            <Layers className="size-3" aria-hidden />
            {runAll.isPending ? "Running all…" : "Run all sources"}
          </Button>
        </div>
      </div>

      <p className="mt-[9px] text-2xs font-light leading-relaxed text-faint">
        Maximum five days per request. Partitions are recorded and resumed, so re-running a window
        never duplicates observations.
      </p>

      {!configured ? (
        <div className="mt-[10px] flex items-start gap-2 rounded-control border border-warn/20 bg-warn/[0.04] px-[12px] py-[9px]">
          <KeyRound className="mt-[1px] size-3 shrink-0 text-warn" aria-hidden />
          <p className="text-2xs font-light leading-relaxed text-muted">
            Live retrieval is disabled because <code className="font-mono">FIRMS_MAP_KEY</code> is
            not set. The labelled fixture can still be loaded with{" "}
            <code className="font-mono">python -m scripts.ingest_fixture --yes</code>.
          </p>
        </div>
      ) : null}

      {error ? (
        <div className="mt-[10px] flex items-start gap-2 rounded-control border border-danger/25 bg-danger/[0.06] px-[12px] py-[9px]">
          <AlertTriangle className="mt-[1px] size-3 shrink-0 text-danger" aria-hidden />
          <div className="text-2xs font-light leading-relaxed text-danger">
            <p>{error instanceof ApiError ? error.message : "Ingestion failed."}</p>
            {error instanceof ApiError && typeof error.details.hint === "string" ? (
              <p className="text-danger/80">{error.details.hint}</p>
            ) : null}
          </div>
        </div>
      ) : null}

      {runAll.data ? (
        <div className="mt-[10px] rounded-control border border-accent/20 bg-accent/[0.04] px-[12px] py-[9px] text-2xs font-light leading-relaxed text-muted">
          <p className="text-ink">
            {runAll.data.sources_succeeded} of {runAll.data.sources_requested} sources ingested
            {runAll.data.sources_failed > 0 ? ` · ${runAll.data.sources_failed} failed` : ""}
          </p>
          <p className="mt-[4px]">
            received {formatCount(runAll.data.records_received)}, inserted{" "}
            {formatCount(runAll.data.records_inserted)}, rejected{" "}
            {formatCount(runAll.data.records_rejected)}
          </p>
          <ul className="mt-[6px] space-y-[2px]">
            {runAll.data.results.map((result) => (
              <li key={result.source_code} className="flex items-center justify-between gap-3">
                <span className="font-mono text-3xs">{result.source_code}</span>
                <span
                  className={
                    result.status === "failed"
                      ? "font-mono text-3xs text-danger"
                      : "font-mono text-3xs text-faint"
                  }
                >
                  {result.status === "failed"
                    ? result.errors[0]?.slice(0, 60) || "failed"
                    : `+${formatCount(result.records_inserted)}`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {runIngestion.data ? (
        <div className="mt-[10px] rounded-control border border-accent/20 bg-accent/[0.04] px-[12px] py-[9px] text-2xs font-light leading-relaxed text-muted">
          <span className="text-ink">
            {runIngestion.data.status} · {runIngestion.data.source_code}
          </span>{" "}
          received {formatCount(runIngestion.data.records_received)}, inserted{" "}
          {formatCount(runIngestion.data.records_inserted)}, rejected{" "}
          {formatCount(runIngestion.data.records_rejected)}. Partitions:{" "}
          {runIngestion.data.partitions_completed} completed,{" "}
          {runIngestion.data.partitions_skipped} skipped.
        </div>
      ) : null}
    </Panel>
  );
}

export function SettingsPage() {
  const { data: status, isError } = useSystemStatus();
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "settings");
  const { data: sources } = useSources();
  const { data: health } = useSourceHealth();
  const { data: runs } = useIngestionRuns();

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
        eyebrow="Firewatch X / System"
        title="Settings & Administration"
        description="Configuration, ingestion control, data-source registry and capability truth for this deployment."
        status={module?.status ?? "in_progress"}
        phase={module?.phase ?? "Phase 1"}
      />

      {isError ? (
        <div className="mb-[12px] flex items-start gap-2.5 rounded-card border border-danger/25 bg-danger/[0.06] px-[18px] py-[13px]">
          <AlertTriangle className="mt-[1px] size-4 shrink-0 text-danger" aria-hidden />
          <p className="text-xs font-light text-danger">
            The API is unreachable, so configuration state cannot be verified.
          </p>
        </div>
      ) : null}

      <div className="mb-[12px] grid gap-[10px] sm:grid-cols-2 xl:grid-cols-4">
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
          label="Observations stored"
          value={formatCount(status?.data.observations_stored)}
          hint={
            status?.data.synthetic_observations
              ? `${formatCount(status.data.synthetic_observations)} synthetic fixture rows`
              : "No synthetic fixture rows"
          }
          tone={status?.data.observations_stored ? "ok" : "warn"}
        />
        <StatTile
          label="API uptime"
          value={status ? formatUptime(status.uptime_seconds) : "—"}
          hint={status ? `Server time ${formatDateTimeUtc(status.server_time)}` : undefined}
        />
      </div>

      <div className="space-y-[12px]">
        <IngestionConsole />

        <div className="grid gap-[12px] lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div className="space-y-[12px]">
            <Panel
              title="Data sources"
              subtitle="The only products this platform supports in the first release."
              bodyClassName="p-0"
            >
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-line/[0.07] text-3xs uppercase tracking-[0.14em] text-faint">
                      <th scope="col" className="px-[22px] py-[9px] font-medium">Source</th>
                      <th scope="col" className="px-3 py-[9px] font-medium">Sensor</th>
                      <th scope="col" className="px-3 py-[9px] font-medium">Level</th>
                      <th scope="col" className="px-3 py-[9px] text-right font-medium">
                        Stored
                      </th>
                      <th scope="col" className="px-[22px] py-[9px] text-right font-medium">
                        State
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {(sources ?? []).map((source) => (
                      <tr
                        key={source.code}
                        className="border-b border-line/[0.05] transition-colors duration-150 last:border-0 hover:bg-line/[0.03]"
                      >
                        <td className="px-[22px] py-[9px]">
                          <div className="font-mono text-2xs text-ink">{source.code}</div>
                          <div className="mt-[1px] text-3xs text-faint">{source.satellite}</div>
                        </td>
                        <td className="px-3 py-[9px] font-light text-muted">{source.sensor}</td>
                        <td className="px-3 py-[9px]">
                          <Badge tone={source.processing_level === "SP" ? "info" : "neutral"}>
                            {source.processing_level}
                          </Badge>
                        </td>
                        <td className="px-3 py-[9px] text-right font-mono text-2xs text-muted">
                          {formatCount(source.observations)}
                        </td>
                        <td className="px-[22px] py-[9px] text-right">
                          <span className="inline-flex items-center gap-1.5 text-2xs font-light text-muted">
                            <StatusDot tone={source.observations ? "ok" : "neutral"} />
                            {source.observations ? "ingested" : "not ingested"}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {!sources ? (
                      <tr>
                        <td colSpan={5} className="px-[22px] py-8 text-center text-xs font-light text-faint">
                          Loading source registry…
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              <p className="border-t border-line/[0.07] px-[22px] py-[11px] text-2xs font-light leading-relaxed text-faint">
                <span className="text-muted">SP</span> = standard processing (historical) ·{" "}
                <span className="text-muted">NRT</span> = near-real-time. Processing versions are
                retained and never combined silently.
              </p>
            </Panel>

            <Panel
              title="Recent ingestion runs"
              subtitle="Every retrieval is audited with its query parameters and counts."
              bodyClassName="p-0"
            >
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-line/[0.07] text-3xs uppercase tracking-[0.14em] text-faint">
                      <th scope="col" className="px-[22px] py-[8px] font-medium">Source</th>
                      <th scope="col" className="px-3 py-[8px] font-medium">Status</th>
                      <th scope="col" className="px-3 py-[8px] text-right font-medium">Received</th>
                      <th scope="col" className="px-3 py-[8px] text-right font-medium">Inserted</th>
                      <th scope="col" className="px-[22px] py-[8px] text-right font-medium">
                        Finished
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {(runs ?? []).map((run) => (
                      <tr
                        key={run.id}
                        className="border-b border-line/[0.05] last:border-0 hover:bg-line/[0.03]"
                      >
                        <td className="px-[22px] py-[8px]">
                          <span className="font-mono text-2xs text-ink">
                            {run.source_code ?? "—"}
                          </span>
                          {run.is_synthetic ? (
                            <Badge tone="warn" className="ml-2">
                              fixture
                            </Badge>
                          ) : null}
                        </td>
                        <td className="px-3 py-[8px]">
                          <Badge tone={run.status === "succeeded" ? "ok" : "warn"}>
                            {run.status}
                          </Badge>
                        </td>
                        <td className="px-3 py-[8px] text-right font-mono text-3xs text-muted">
                          {formatCount(run.records_received)}
                        </td>
                        <td className="px-3 py-[8px] text-right font-mono text-3xs text-muted">
                          {formatCount(run.records_inserted)}
                        </td>
                        <td className="px-[22px] py-[8px] text-right font-mono text-3xs text-faint">
                          {formatDateTimeUtc(run.completed_at ?? run.started_at)}
                        </td>
                      </tr>
                    ))}
                    {(runs ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-[22px] py-8 text-center text-xs font-light text-faint">
                          No ingestion runs recorded yet.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>

          <div className="space-y-[12px]">
            <Panel
              title="Capabilities"
              subtitle="Reported by /api/v1/system/status — not marketing copy."
              bodyClassName="p-0"
            >
              <ul>
                <CapabilityRow
                  label="NASA ingestion"
                  enabled={status?.capabilities.ingestion ?? false}
                  note="Implemented in Phase 2; reports false only when FIRMS_MAP_KEY is unset."
                />
                <CapabilityRow
                  label="Harmonization engine"
                  enabled
                  note="Cross-sensor association and event grouping (Phase 3)."
                />
                <CapabilityRow
                  label="Spatial queries"
                  enabled={status?.capabilities.spatial ?? false}
                  note="PostGIS required; SQLite reports false."
                />
                <CapabilityRow
                  label="Authentication & RBAC"
                  enabled={false}
                  note="Argon2id, roles and sessions arrive in the security phase."
                />
                <CapabilityRow
                  label="Rate limiting"
                  enabled={false}
                  note="Per-client limits for public endpoints."
                />
                <CapabilityRow
                  label="Reports & exports"
                  enabled={false}
                  note="PDF, CSV, GeoJSON and JSON with methodology."
                />
                <CapabilityRow
                  label="AI assistant"
                  enabled={status?.capabilities.ai_assistant ?? false}
                  note="Tool-calling over approved functions only."
                />
              </ul>
            </Panel>

            <Panel title="Source health" subtitle="Last run per registered product." bodyClassName="p-0">
              <ul>
                {(health ?? [])
                  .filter((item) => item.observations > 0 || item.last_run_at)
                  .slice(0, 6)
                  .map((item) => (
                    <li
                      key={item.code}
                      className="flex items-center justify-between gap-3 border-b border-line/[0.06] px-[22px] py-[9px] last:border-0"
                    >
                      <div className="min-w-0">
                        <div className="font-mono text-2xs text-ink">{item.code}</div>
                        <div className="mt-[1px] text-3xs text-faint">
                          {formatCount(item.observations)} observations
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <Badge tone={item.last_run_status === "succeeded" ? "ok" : "neutral"}>
                          {item.last_run_status ?? "never run"}
                        </Badge>
                        <div className="mt-[3px] font-mono text-3xs text-faint">
                          {formatDateTimeUtc(item.last_run_at)}
                        </div>
                      </div>
                    </li>
                  ))}
                {(health ?? []).filter((item) => item.observations > 0 || item.last_run_at).length ===
                0 ? (
                  <li className="px-[22px] py-6 text-center text-xs font-light text-faint">
                    No source has run yet.
                  </li>
                ) : null}
              </ul>
            </Panel>

            <Panel title="Required configuration" subtitle="Read by the API at startup." bodyClassName="p-0">
              <ul>
                {config.map((item) => (
                  <li
                    key={item.name}
                    className="border-b border-line/[0.06] px-[22px] py-[10px] last:border-0"
                  >
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
                    <p className="mt-[3px] text-2xs font-light leading-relaxed text-faint">
                      {item.purpose}
                    </p>
                  </li>
                ))}
              </ul>
            </Panel>

            <div className="rounded-card border border-warn/20 bg-warn/[0.04] px-[18px] py-[14px]">
              <div className="mb-[6px] flex items-center gap-2">
                <AlertTriangle className="size-3.5 text-warn" aria-hidden />
                <span className="text-xs text-ink">Evidence standard</span>
              </div>
              <p className="text-2xs font-light leading-relaxed text-muted">
                Every analytical value reconciles with stored observations and keeps NASA
                attribution visible. Synthetic fixture rows are labelled everywhere they appear.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
