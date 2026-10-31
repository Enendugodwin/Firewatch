import { AlertTriangle, ArrowUpRight, CheckCircle2, CircleDashed, KeyRound } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel, StatTile } from "@/components/ui/Panel";
import { StatusDot } from "@/components/ui/StatusDot";
import { SyntheticBanner } from "@/components/ui/SyntheticBanner";
import { findNavItemByKey } from "@/config/nav";
import { useDashboardOverview, useModules, useSystemStatus } from "@/lib/queries";
import { formatCount, formatFrp } from "@/lib/format";
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
  const { data: status, isError: statusError } = useSystemStatus();
  const overview = useDashboardOverview();
  const { data: modules } = useModules();
  const dateRange = useUiStore((state) => state.dateRange);

  const navItem = findNavItemByKey("overview");
  const module = modules?.find((item) => item.key === "overview");

  const data = overview.data;
  const total = data?.detections.total ?? 0;
  const hasData = total > 0;

  const stages: Stage[] = [
    {
      name: "Platform foundation",
      phase: "Phase 1",
      detail: "API, configuration, design system, navigation and db registry.",
      state: "done",
    },
    {
      name: "NASA FIRMS credential",
      phase: "Phase 2",
      detail: status?.data.firms_configured
        ? "FIRMS_MAP_KEY is present in the backend environment."
        : "Set FIRMS_MAP_KEY in the backend environment to enable live retrieval.",
      state: status?.data.firms_configured ? "done" : "blocked",
    },
    {
      name: "Ingestion and normalization",
      phase: "Phase 2",
      detail: "Tiled, resumable retrieval; raw payloads retained; per-sensor adapters.",
      state: "done",
    },
    {
      name: "MODIS/VIIRS harmonization",
      phase: "Phase 3",
      detail: "Cross-sensor association scoring, event grouping and inspection.",
      state: "done",
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
    <div>
      <PageHeader
        eyebrow="Firewatch X / Monitoring"
        title={module?.label ?? navItem?.label ?? "Overview"}
        description="Global fire activity and intelligence summary, computed from stored satellite observations."
        status={module?.status ?? "in_progress"}
        phase={module?.phase ?? "Phase 4"}
      />

      {statusError || overview.isError ? (
        <div className="mb-[12px] flex items-start gap-2.5 rounded-card border border-danger/25 bg-danger/[0.06] px-[18px] py-[13px]">
          <AlertTriangle className="mt-[1px] size-4 shrink-0 text-danger" aria-hidden />
          <div className="text-xs font-light leading-relaxed text-danger">
            <p className="font-medium">The API is not reachable.</p>
            <p className="mt-[2px] text-danger/80">
              Every figure on this page is withheld rather than guessed.
            </p>
          </div>
        </div>
      ) : null}

      <SyntheticBanner count={data?.data.synthetic_observations ?? 0} total={total} />

      <div className="grid gap-[10px] sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Detections in period"
          value={formatCount(total)}
          hint={
            total
              ? `${formatCount(data?.detections.modis)} MODIS · ${formatCount(
                  data?.detections.viirs,
                )} VIIRS`
              : "No observations stored yet"
          }
          tone={total ? "neutral" : "warn"}
        />
        <StatTile
          label="Cross-sensor matches"
          value={formatCount(data?.matches.total)}
          hint={
            data?.scope?.start_date
              ? `${formatCount(data?.matches.probable)} probable · ${formatCount(
                  data?.matches.possible,
                )} possible (last scope)`
              : "Recompute associations to populate"
          }
        />
        <StatTile
          label="Estimated events"
          value={formatCount(data?.events)}
          hint={
            data?.scope?.start_date
              ? `Estimated clusters, scope ${data.scope.start_date}`
              : "Estimated clusters from the last run"
          }
        />
        <StatTile
          label="Aggregate FRP"
          value={total ? formatFrp(data?.detections.frp_mw) : "—"}
          hint="Summed Fire Radiative Power of stored detections"
        />
      </div>

      <p className="mt-[10px] text-2xs font-light leading-relaxed text-faint">
        {data?.note ??
          "Counts are satellite thermal detections, not fires. Detection totals cover the whole store; match and event counts cover the last analysis scope."}
      </p>

      <div className="mt-[12px] grid gap-[12px] lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-[12px]">
          <Panel
            title="Pipeline readiness"
            subtitle="Real system state — nothing here is simulated."
            actions={<Badge tone={hasData ? "ok" : "warn"}>{hasData ? "data present" : "no data yet"}</Badge>}
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

          {hasData ? (
            <Panel
              title="Where to go next"
              subtitle="The map and calendar arrive in Phases 4 and 5; the association workspace is live."
            >
              <div className="flex flex-wrap gap-2">
                <Link
                  to="/harmonization"
                  className="inline-flex items-center gap-1.5 rounded-full border border-line/10 bg-line/[0.03] px-3 py-1.5 text-xs font-light text-muted transition-colors duration-150 hover:text-ink"
                >
                  Inspect sensor intelligence
                  <ArrowUpRight className="size-3" aria-hidden />
                </Link>
                <Link
                  to="/settings"
                  className="inline-flex items-center gap-1.5 rounded-full border border-line/10 bg-line/[0.03] px-3 py-1.5 text-xs font-light text-muted transition-colors duration-150 hover:text-ink"
                >
                  Ingestion and sources
                  <ArrowUpRight className="size-3" aria-hidden />
                </Link>
              </div>
            </Panel>
          ) : (
            <EmptyState
              title="No fire activity to display"
              description="The overview will show a global heatmap, daily detection trend and top regions once observations exist. Today the pipeline is empty, so this page reports system state instead of inventing a picture."
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
          )}
        </div>

        <div className="space-y-[12px]">
          <Panel
            title="Data ingestion status"
            subtitle="Separate indicators so a refreshing page is never mistaken for a live feed."
            actions={
              <span className="inline-flex items-center gap-1.5 text-2xs font-light text-muted">
                <StatusDot tone={status?.database.connected ? "ok" : "danger"} />
                {status?.database.connected ? "database reachable" : "database down"}
              </span>
            }
          >
            <dl className="divide-y divide-line/[0.06]">
              <div className="flex items-center justify-between gap-3 py-[7px]">
                <dt className="text-2xs font-light text-faint">Last ingestion</dt>
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
                  {formatCount(status?.data.observations_stored)}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3 py-[7px]">
                <dt className="text-2xs font-light text-faint">Missing dates</dt>
                <dd className="font-mono text-2xs text-muted">
                  {formatCount(status?.data.missing_dates)}
                </dd>
              </div>
            </dl>
            <p className="mt-[10px] border-t border-line/[0.06] pt-[10px] text-2xs font-light leading-relaxed text-faint">
              {status?.data.freshness_reason ?? "Freshness is unknown until the API responds."}
            </p>
          </Panel>

          <Panel title="Selected period" subtitle="Shared across every module.">
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
        </div>
      </div>
    </div>
  );
}
