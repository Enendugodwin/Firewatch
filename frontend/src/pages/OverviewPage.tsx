import { AlertTriangle, ArrowUpRight, CheckCircle2, CircleDashed, KeyRound } from "lucide-react";
import { Link } from "react-router-dom";

import { ModuleScaffold } from "@/components/ui/ModuleScaffold";
import { Panel, StatTile } from "@/components/ui/Panel";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusDot } from "@/components/ui/StatusDot";
import { useModules, useSystemStatus } from "@/lib/queries";
import { formatDateTimeUtc, formatUptime } from "@/lib/time";
import { useUiStore } from "@/store/ui";

type StageState = "done" | "active" | "blocked" | "pending";

const STAGE_LABEL: Record<StageState, { tone: "ok" | "info" | "warn" | "neutral"; label: string }> = {
  done: { tone: "ok", label: "Ready" },
  active: { tone: "info", label: "In progress" },
  blocked: { tone: "warn", label: "Blocked" },
  pending: { tone: "neutral", label: "Pending" },
};

interface Stage {
  name: string;
  phase: string;
  detail: string;
  state: StageState;
}

export function OverviewPage() {
  const { data: status, isError, error, isLoading } = useSystemStatus();
  const { data: modules } = useModules();
  const dateRange = useUiStore((state) => state.dateRange);

  const overviewModule = modules?.find((module) => module.key === "overview");

  const stages: Stage[] = [
    {
      name: "Platform foundation",
      phase: "Phase 1",
      detail: "API, configuration, design system, navigation and database registry.",
      state: "done",
    },
    {
      name: "NASA FIRMS credential",
      phase: "Phase 2",
      detail: status?.data.firms_configured
        ? "FIRMS_MAP_KEY is present in the backend environment."
        : "Set FIRMS_MAP_KEY in the backend environment to enable retrieval.",
      state: status?.data.firms_configured ? "done" : "blocked",
    },
    {
      name: "Ingestion and normalization",
      phase: "Phase 2",
      detail: "Tiled, resumable retrieval of MODIS and VIIRS records into PostGIS.",
      state: "pending",
    },
    {
      name: "MODIS/VIIRS harmonization",
      phase: "Phase 3",
      detail: "Cross-sensor association scoring and optional event clustering.",
      state: "pending",
    },
    {
      name: "Global fire map",
      phase: "Phase 4",
      detail: "MapLibre layers, filters and hotspot inspection with provenance.",
      state: "pending",
    },
    {
      name: "Historical burning calendar",
      phase: "Phase 5",
      detail: "Daily to annual aggregation with missing-data awareness.",
      state: "pending",
    },
    {
      name: "Anomaly detection",
      phase: "Phase 6",
      detail: "Seasonal baselines and MAD-based deviation with explanations.",
      state: "pending",
    },
  ];

  return (
    <ModuleScaffold
      moduleKey="overview"
      requirements={[
        "A NASA FIRMS MAP_KEY stored in the backend environment (never the browser).",
        "PostgreSQL with PostGIS reachable from the API for spatial storage.",
        "A completed ingestion run, so statistics are computed from stored observations.",
      ]}
      extra={
        <div className="mb-[12px] space-y-[12px]">
          {isError ? (
            <div className="flex items-start gap-2.5 rounded-card border border-danger/25 bg-danger/[0.06] px-[18px] py-[14px]">
              <AlertTriangle className="mt-[2px] size-4 shrink-0 text-danger" aria-hidden />
              <div className="text-xs font-light leading-relaxed text-danger">
                <p className="font-medium">The API is not reachable.</p>
                <p className="mt-[2px] text-danger/80">
                  {error instanceof Error ? error.message : "Unknown error."} Every figure on this
                  page is withheld rather than guessed.
                </p>
              </div>
            </div>
          ) : null}

          <div className="grid gap-[10px] sm:grid-cols-2 xl:grid-cols-4">
            <StatTile
              label="Detections in period"
              value={isLoading ? "…" : "—"}
              hint={
                status?.data.freshness === "no_data"
                  ? "No observations stored yet"
                  : "Computed from stored observations only"
              }
              tone="warn"
            />
            <StatTile
              label="MODIS / VIIRS"
              value={isLoading ? "…" : "— / —"}
              hint="Split appears once both sensor families are ingested"
            />
            <StatTile
              label="Cross-sensor matches"
              value={isLoading ? "…" : "—"}
              hint="Requires Phase 3 harmonization"
            />
            <StatTile
              label="Sources registered"
              value={isLoading ? "…" : String(status?.data.sources_registered ?? "—")}
              hint="NASA FIRMS products in the catalogue"
            />
          </div>

          <Panel
            title="Pipeline readiness"
            subtitle="Real system state — nothing here is simulated."
            actions={<Badge tone="warn">no data yet</Badge>}
            bodyClassName="p-0"
          >
            <ul>
              {stages.map((stage) => {
                const style = STAGE_LABEL[stage.state];
                return (
                  <li
                    key={stage.name}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line/[0.06] px-[22px] py-[11px] last:border-0"
                  >
                    {stage.state === "done" ? (
                      <CheckCircle2 className="size-3.5 shrink-0 text-accent" aria-hidden />
                    ) : stage.state === "blocked" ? (
                      <KeyRound className="size-3.5 shrink-0 text-warn" aria-hidden />
                    ) : (
                      <CircleDashed className="size-3.5 shrink-0 text-faint" aria-hidden />
                    )}
                    <span className="text-xs text-ink">{stage.name}</span>
                    <span className="font-mono text-3xs text-faint">{stage.phase}</span>
                    <span className="w-full text-2xs font-light leading-relaxed text-muted sm:ml-[26px] sm:w-auto sm:flex-1">
                      {stage.detail}
                    </span>
                    <Badge tone={style.tone}>{style.label}</Badge>
                  </li>
                );
              })}
            </ul>
          </Panel>

          <div className="grid gap-[12px] lg:grid-cols-2">
            <Panel
              title="Selected period"
              subtitle="Shared across every module once queries are live."
            >
              <dl className="grid grid-cols-2 gap-x-[18px] gap-y-[14px]">
                <div>
                  <dt className="label">Start (UTC)</dt>
                  <dd className="mt-[6px] font-mono text-[13px] text-ink">{dateRange.start}</dd>
                </div>
                <div>
                  <dt className="label">End (UTC)</dt>
                  <dd className="mt-[6px] font-mono text-[13px] text-ink">{dateRange.end}</dd>
                </div>
                <div>
                  <dt className="label">Preset</dt>
                  <dd className="mt-[6px] text-xs font-light capitalize text-muted">
                    {dateRange.preset}
                  </dd>
                </div>
                <div>
                  <dt className="label">API uptime</dt>
                  <dd className="mt-[6px] font-mono text-[13px] text-ink">
                    {status ? formatUptime(status.uptime_seconds) : "—"}
                  </dd>
                </div>
              </dl>
            </Panel>

            <Panel
              title="Data ingestion status"
              subtitle="Separate indicators so a refreshing map is never mistaken for a live feed."
              actions={
                <span className="inline-flex items-center gap-1.5 text-2xs font-light text-muted">
                  <StatusDot tone={status?.database.connected ? "ok" : "danger"} />
                  {status?.database.connected ? "database reachable" : "database down"}
                </span>
              }
            >
              <dl className="divide-y divide-line/[0.06]">
                <div className="flex items-center justify-between gap-3 py-[7px]">
                  <dt className="text-2xs font-light text-faint">Last NRT retrieval</dt>
                  <dd className="font-mono text-2xs text-muted">
                    {formatDateTimeUtc(status?.data.last_ingested_at ?? null)}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3 py-[7px]">
                  <dt className="text-2xs font-light text-faint">Latest observation</dt>
                  <dd className="font-mono text-2xs text-muted">
                    {formatDateTimeUtc(status?.data.last_observation_at ?? null)}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3 py-[7px]">
                  <dt className="text-2xs font-light text-faint">Observations stored</dt>
                  <dd className="font-mono text-2xs text-muted">
                    {status?.data.observations_stored ?? "—"}
                  </dd>
                </div>
              </dl>
              <p className="mt-[10px] border-t border-line/[0.06] pt-[10px] text-2xs font-light leading-relaxed text-faint">
                {status?.data.freshness_reason ?? "Freshness is unknown until the API responds."}
              </p>
            </Panel>
          </div>

          <EmptyState
            title="No fire activity to display"
            description={
              <>
                The overview will show a global heatmap, daily detection trend and top regions once
                observations exist. Today the pipeline is empty, so this page reports system state
                instead of inventing a picture.
              </>
            }
            action={
              <Link
                to="/settings"
                className="inline-flex items-center gap-1.5 text-xs font-light text-accent transition-colors duration-150 hover:text-ink"
              >
                Inspect sources and configuration
                <ArrowUpRight className="size-3" aria-hidden />
              </Link>
            }
          />
        </div>
      }
    >
      <Panel title="What this module delivers" subtitle={overviewModule?.phase ?? "Phase 4"}>
        <ul className="space-y-[10px]">
          {(overviewModule?.planned ?? []).map((item) => (
            <li key={item} className="flex gap-3 text-xs font-light leading-relaxed text-muted">
              <span className="mt-[7px] size-1 shrink-0 rounded-full bg-accent/60" />
              {item}
            </li>
          ))}
        </ul>
      </Panel>
    </ModuleScaffold>
  );
}
