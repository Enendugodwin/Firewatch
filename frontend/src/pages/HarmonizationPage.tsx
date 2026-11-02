import { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FlaskConical,
  GitCompare,
  Layers,
  RotateCw,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingBlock } from "@/components/ui/LoadingCue";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel, StatTile } from "@/components/ui/Panel";
import { Download } from "lucide-react";
import { StatusDot } from "@/components/ui/StatusDot";
import { SyntheticBanner } from "@/components/ui/SyntheticBanner";
import { AssociationScore } from "@/components/ui/AssociationScore";
import { findNavItemByKey } from "@/config/nav";
import { useUiStore } from "@/store/ui";
import { useHarmonizedSeries, useModules } from "@/lib/queries";
import {
  useAlgorithmRuns,
  useEvents,
  useHarmonizationSummary,
  useMatches,
  useRunHarmonization,
  useSources,
} from "@/lib/queries";
import {
  formatCount,
  formatCoordinate,
  formatDeltaSeconds,
  formatDistance,
  formatFrp,
  formatPercent,
} from "@/lib/format";
import { formatDateTimeUtc } from "@/lib/time";
import type { MatchStatus, ObservationMatch } from "@/types/api";

const STATUS_TABS: { value: MatchStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "probable", label: "Probable" },
  { value: "possible", label: "Possible" },
  { value: "rejected", label: "Rejected" },
];

const STATUS_TONE: Record<MatchStatus, "ok" | "info" | "neutral"> = {
  probable: "ok",
  possible: "info",
  rejected: "neutral",
};

function SensorChip({ sensor }: { sensor: string }) {
  return (
    <span className="rounded-tag border border-line/[0.1] px-1.5 py-[1px] font-mono text-3xs uppercase tracking-[0.08em] text-muted">
      {sensor}
    </span>
  );
}

function MatchEvidence({ match }: { match: ObservationMatch }) {
  const temporal = match.components.temporal_similarity ?? 0;
  const spatial = match.components.spatial_proximity ?? 0;
  const footprint = match.components.footprint_overlap;

  const rows: { label: string; value: number | null | undefined }[] = [
    { label: "Temporal similarity", value: temporal },
    { label: "Geographic proximity", value: spatial },
    { label: "Footprint overlap", value: footprint },
  ];

  return (
    <div className="space-y-[12px]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="label">Association score</div>
          <div className="mt-[6px] flex items-baseline gap-2">
            <span className="font-display text-[28px] leading-none text-ink">
              {match.association_score.toFixed(3)}
            </span>
            <Badge tone={STATUS_TONE[match.match_status]}>{match.match_status}</Badge>
          </div>
        </div>
        <GitCompare className="size-4 text-faint" aria-hidden />
      </div>

      <div className="space-y-[9px]">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="flex items-center justify-between text-2xs">
              <span className="font-light text-faint">{row.label}</span>
              <span className="font-mono text-muted">
                {row.value === null || row.value === undefined ? "n/a" : formatPercent(row.value)}
              </span>
            </div>
            <div className="mt-[4px] h-[2px] overflow-hidden rounded-full bg-line/10">
              <div
                className="h-full rounded-full bg-accent/70"
                style={{ width: `${Math.round((row.value ?? 0) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <p className="border-t border-line/[0.06] pt-[9px] text-2xs font-light leading-relaxed text-faint">
        {typeof match.components.weight_note === "string"
          ? match.components.weight_note
          : null}{" "}
        · algorithm <span className="font-mono text-muted">{match.algorithm_version}</span>
      </p>

      <div className="space-y-[8px]">
        {[match.observation_a, match.observation_b].map((observation, index) => (
          <div
            key={observation.id}
            className="rounded-control border border-line/[0.07] bg-line/[0.02] px-[10px] py-[9px]"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="inline-flex items-center gap-1.5">
                <span className="text-3xs text-faint">{index === 0 ? "A" : "B"}</span>
                <SensorChip sensor={observation.sensor} />
                <span className="text-2xs text-muted">{observation.satellite}</span>
              </span>
              <span className="font-mono text-3xs text-faint">{observation.source_code}</span>
            </div>
            <div className="mt-[6px] grid grid-cols-2 gap-x-2 gap-y-[3px] font-mono text-3xs text-muted">
              <span>
                {formatCoordinate(observation.latitude)}, {formatCoordinate(observation.longitude)}
              </span>
              <span className="text-right">{formatDateTimeUtc(observation.acquired_at)}</span>
              <span>FRP {formatFrp(observation.frp_mw)}</span>
              <span className="text-right">
                conf {observation.confidence_category ?? "—"}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-[3px] border-t border-line/[0.06] pt-[9px]">
        <div className="label">Observation identifiers</div>
        <p className="truncate font-mono text-3xs text-faint">{match.observation_a.id}</p>
        <p className="truncate font-mono text-3xs text-faint">{match.observation_b.id}</p>
      </div>

      <p className="text-2xs font-light leading-relaxed text-faint">
        An association score is not the probability that both detections are the same physical
        fire. Observations are never merged.
      </p>
    </div>
  );
}

export function HarmonizationPage() {
  const navItem = findNavItemByKey("harmonization");
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "harmonization");

  const summary = useHarmonizationSummary();
  const [statusFilter, setStatusFilter] = useState<MatchStatus | "all">("all");
  const matches = useMatches(statusFilter === "all" ? undefined : statusFilter);
  const events = useEvents();
  const sources = useSources();
  const runs = useAlgorithmRuns();
  const runHarmonization = useRunHarmonization();
  const dateRange = useUiStore((state) => state.dateRange);
  const harmonized = useHarmonizedSeries(dateRange.start, dateRange.end);

  const [selectedId, setSelectedId] = useState<string | null>(null);

  const data = summary.data;
  const matchItems = matches.data?.items ?? [];
  const selected =
    matchItems.find((item) => item.id === selectedId) ?? matchItems[0] ?? null;

  const ingestedSources = (sources.data ?? []).filter((source) => source.observations > 0);
  const hasData = (data?.observations ?? 0) > 0;

  const headerActions = (
    <div className="flex items-center gap-2">
      {data?.last_run_at ? (
        <span className="hidden items-center gap-1.5 text-2xs font-light text-faint sm:inline-flex">
          <StatusDot tone={data.last_run_status === "succeeded" ? "ok" : "warn"} />
          last run {formatDateTimeUtc(data.last_run_at)}
        </span>
      ) : null}
      <Button
        variant="primary"
        onClick={() =>
          runHarmonization.mutate({ start_date: dateRange.start, end_date: dateRange.end })
        }
        disabled={!hasData || runHarmonization.isPending}
        title={
          hasData
            ? "Recompute associations and estimated events from stored observations"
            : "Ingest observations first"
        }
      >
        {runHarmonization.isPending ? (
          <RotateCw className="size-3.5 animate-spin" aria-hidden />
        ) : (
          <GitCompare className="size-3.5" aria-hidden />
        )}
        {runHarmonization.isPending ? "Recomputing…" : "Re-run associations"}
      </Button>
    </div>
  );

  return (
    <div>
      <PageHeader
        eyebrow="Firewatch X / Sensor Intelligence"
        title={module?.label ?? navItem?.label ?? "Sensor Intelligence"}
        description="MODIS and VIIRS normalization, cross-sensor association and estimated event grouping. Raw observations are preserved and never merged."
        status={module?.status ?? "ready"}
        phase={module?.phase ?? "Phase 3"}
        actions={headerActions}
      />

      {summary.isError ? (
        <div className="mb-[12px] flex items-start gap-2.5 rounded-card border border-danger/25 bg-danger/[0.06] px-[18px] py-[12px]">
          <AlertTriangle className="mt-[1px] size-4 shrink-0 text-danger" aria-hidden />
          <p className="text-xs font-light text-danger">
            The harmonization API is unreachable, so no association results are shown.
          </p>
        </div>
      ) : null}

      <SyntheticBanner
        count={data?.synthetic_observations ?? 0}
        total={data?.observations ?? 0}
      />

      {runHarmonization.isError ? (
        <div className="mb-[12px] flex items-start gap-2.5 rounded-card border border-danger/25 bg-danger/[0.06] px-[18px] py-[12px]">
          <AlertTriangle className="mt-[1px] size-4 shrink-0 text-danger" aria-hidden />
          <p className="text-xs font-light text-danger">
            Recompute failed. {String((runHarmonization.error as Error).message)}
          </p>
        </div>
      ) : null}

      {runHarmonization.isSuccess ? (
        <div className="mb-[12px] flex items-start gap-2.5 rounded-card border border-accent/20 bg-accent/[0.04] px-[18px] py-[12px]">
          <CheckCircle2 className="mt-[1px] size-3.5 shrink-0 text-accent" aria-hidden />
          <p className="text-2xs font-light text-muted">
            Recompute complete for{" "}
            <span className="text-ink">{runHarmonization.data?.scopes.length ?? 0}</span>{" "}
            provenance scope(s); events regrouped. Results below reflect the stored observations.
          </p>
        </div>
      ) : null}

      <div className="mb-[12px] grid gap-[10px] sm:grid-cols-2 xl:grid-cols-5">
        <StatTile
          label="Detections stored"
          value={formatCount(data?.observations)}
          hint="Raw satellite observations"
        />
        <StatTile
          label="MODIS"
          value={formatCount(data?.modis_observations)}
          hint="1 km product family"
        />
        <StatTile
          label="VIIRS"
          value={formatCount(data?.viirs_observations)}
          hint="375 m product family"
        />
        <StatTile
          label="Cross-sensor matches"
          value={formatCount((data?.matches_probable ?? 0) + (data?.matches_possible ?? 0))}
          hint={`${formatCount(data?.matches_probable)} probable · ${formatCount(
            data?.matches_possible,
          )} possible`}
          tone="ok"
        />
        <StatTile
          label="Estimated events"
          value={formatCount(data?.events)}
          hint={`${formatCount(data?.multi_sensor_events)} seen by both sensors`}
        />
      </div>

      <p className="mb-[12px] text-2xs font-light leading-relaxed text-faint">
        Detection totals cover the whole store. Association and event results cover the last
        analysis scope
        {data?.last_run_scope?.start_date
          ? ` (${data.last_run_scope.start_date} → ${data.last_run_scope.end_date ?? "…"}${
              data.last_run_scope.bbox
                ? `, bbox ${data.last_run_scope.bbox.join(", ")}`
                : ""
            })`
          : " (not yet scoped)"}
        . Re-running uses the period selected in the header.
      </p>

      {!hasData && !summary.isLoading ? (
        <EmptyState
          title="No observations to harmonize"
          description="Ingestion and harmonization are implemented, but this database holds no observations. Load the labelled fixture for a pipeline demo, or configure FIRMS_MAP_KEY and run an ingestion window from Settings."
        />
      ) : (
        <>
          <div className="grid gap-[12px] xl:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
            <Panel
              title="Cross-sensor associations"
              subtitle="Candidate pairs from different sensor families within the time and distance windows."
              bodyClassName="p-0"
              actions={
                <div className="flex items-center gap-[6px]">
                <div className="flex gap-[2px]">
                  {STATUS_TABS.map((tab) => (
                    <button
                      key={tab.value}
                      type="button"
                      onClick={() => setStatusFilter(tab.value)}
                      className={`rounded-full px-2.5 py-[3px] text-3xs uppercase tracking-[0.12em] transition-colors duration-150 ${
                        statusFilter === tab.value
                          ? "bg-line/[0.08] text-ink"
                          : "text-faint hover:text-muted"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                <a
                  href={`/api/v1/harmonization/matches.csv${
                    statusFilter === "all" ? "" : `?status=${statusFilter}`
                  }`}
                  download
                  className="btn-glass inline-flex items-center gap-1.5 px-2.5 py-[4px] text-3xs"
                  title="Download the current filter as CSV"
                >
                  <Download className="size-3" aria-hidden />
                  Export CSV
                </a>
                </div>
              }
            >
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-line/[0.07] text-3xs uppercase tracking-[0.12em] text-faint">
                      <th scope="col" className="px-[22px] py-[8px] font-medium">Pair</th>
                      <th scope="col" className="px-3 py-[8px] font-medium">Score</th>
                      <th scope="col" className="px-3 py-[8px] font-medium">Δ time</th>
                      <th scope="col" className="px-3 py-[8px] font-medium">Distance</th>
                      <th scope="col" className="px-[22px] py-[8px] text-right font-medium">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {matchItems.map((match) => (
                      <tr
                        key={match.id}
                        onClick={() => setSelectedId(match.id)}
                        className={`cursor-pointer border-b border-line/[0.05] transition-colors duration-150 last:border-0 ${
                          selected?.id === match.id ? "bg-line/[0.05]" : "hover:bg-line/[0.03]"
                        }`}
                      >
                        <td className="px-[22px] py-[8px]">
                          <span className="inline-flex items-center gap-1.5">
                            <SensorChip sensor={match.observation_a.sensor} />
                            <ArrowRight className="size-2.5 text-faint" aria-hidden />
                            <SensorChip sensor={match.observation_b.sensor} />
                          </span>
                        </td>
                        <td className="px-3 py-[8px]">
                          <AssociationScore
                            score={match.association_score}
                            status={match.match_status}
                            compact
                          />
                        </td>
                        <td className="px-3 py-[8px] font-mono text-3xs text-muted">
                          {formatDeltaSeconds(match.temporal_delta_seconds)}
                        </td>
                        <td className="px-3 py-[8px] font-mono text-3xs text-muted">
                          {formatDistance(match.spatial_distance_m)}
                        </td>
                        <td className="px-[22px] py-[8px] text-right">
                          <Badge tone={STATUS_TONE[match.match_status]}>
                            {match.match_status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                    {matchItems.length === 0 ? (
                      <tr>
                        <td
                          colSpan={5}
                          className="px-[22px] py-10 text-center text-xs font-light text-faint"
                        >
                          {matches.isLoading
                            ? "Loading associations…"
                            : "No associations for this filter."}
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              <p className="border-t border-line/[0.07] px-[22px] py-[10px] text-2xs font-light leading-relaxed text-faint">
                Only different sensor families are compared. MODIS and VIIRS brightness channels
                are kept separate — they are not interchangeable measurements.
              </p>
            </Panel>

            <Panel
              title="Match evidence"
              subtitle="Every component of the score is inspectable."
              actions={
                selected ? (
                  <Badge tone={STATUS_TONE[selected.match_status]}>{selected.match_status}</Badge>
                ) : null
              }
            >
              {selected ? (
                <MatchEvidence match={selected} />
              ) : (
                <p className="py-6 text-center text-xs font-light text-faint">
                  Select an association to inspect its evidence.
                </p>
              )}
            </Panel>
          </div>

          <div className="mt-[12px] grid gap-[12px] xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
            <Panel
              title="Estimated fire events"
              subtitle="Spatiotemporal clusters. An event is an estimate, not a confirmed fire and not continuous monitoring."
              bodyClassName="p-0"
            >
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-line/[0.07] text-3xs uppercase tracking-[0.12em] text-faint">
                      <th scope="col" className="px-[22px] py-[8px] font-medium">Centroid</th>
                      <th scope="col" className="px-3 py-[8px] font-medium">Observations</th>
                      <th scope="col" className="px-3 py-[8px] font-medium">Sensors</th>
                      <th scope="col" className="px-3 py-[8px] font-medium">Peak FRP</th>
                      <th scope="col" className="px-[22px] py-[8px] text-right font-medium">
                        Window
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {(events.data ?? []).map((event) => (
                      <tr
                        key={event.id}
                        className="border-b border-line/[0.05] last:border-0 hover:bg-line/[0.03]"
                      >
                        <td className="px-[22px] py-[8px] font-mono text-3xs text-muted">
                          {formatCoordinate(event.centroid_latitude)},{" "}
                          {formatCoordinate(event.centroid_longitude)}
                        </td>
                        <td className="px-3 py-[8px] font-mono text-3xs text-ink">
                          {event.observation_count}
                        </td>
                        <td className="px-3 py-[8px]">
                          <span className="inline-flex items-center gap-1">
                            <Layers className="size-3 text-faint" aria-hidden />
                            <span className="text-2xs text-muted">{event.sensor_count}</span>
                          </span>
                        </td>
                        <td className="px-3 py-[8px] font-mono text-3xs text-muted">
                          {formatFrp(event.maximum_frp_mw)}
                        </td>
                        <td className="px-[22px] py-[8px] text-right font-mono text-3xs text-faint">
                          {formatDateTimeUtc(event.first_detected_at)} →{" "}
                          {formatDateTimeUtc(event.last_detected_at)}
                        </td>
                      </tr>
                    ))}
                    {(events.data ?? []).length === 0 ? (
                      <tr>
                        <td
                          colSpan={5}
                          className="px-[22px] py-8 text-center text-xs font-light text-faint"
                        >
                          No estimated events. Run associations to regroup observations.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </Panel>

            <div className="space-y-[12px]">
              <Panel
                title="Normalized sources"
                subtitle="Counts from stored observations, per FIRMS product."
                bodyClassName="p-0"
              >
                <ul>
                  {ingestedSources.map((source) => (
                    <li
                      key={source.code}
                      className="flex items-center justify-between gap-3 border-b border-line/[0.06] px-[22px] py-[9px] last:border-0"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-2xs text-ink">{source.code}</span>
                          <Badge tone={source.processing_level === "SP" ? "info" : "neutral"}>
                            {source.processing_level}
                          </Badge>
                        </div>
                        <div className="mt-[2px] text-3xs font-light text-faint">
                          {source.sensor} · {source.satellite}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-xs text-ink">
                          {formatCount(source.observations)}
                        </div>
                        <div className="text-3xs text-faint">
                          {formatDateTimeUtc(source.last_observation_at)}
                        </div>
                      </div>
                    </li>
                  ))}
                  {ingestedSources.length === 0 ? (
                    <li className="px-[22px] py-6 text-center text-xs font-light text-faint">
                      No source has stored observations yet.
                    </li>
                  ) : null}
                </ul>
              </Panel>

              <Panel
                title="Harmonized series"
                subtitle="Raw detections minus VIIRS detections already associated with MODIS. Raw sensor series are unchanged."
              >
                {harmonized.isLoading ? (
                  <LoadingBlock label="Building the harmonized series…" lines={3} />
                ) : harmonized.data ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      {[
                        ["MODIS", harmonized.data.totals.modis],
                        ["VIIRS", harmonized.data.totals.viirs],
                        ["Raw combined", harmonized.data.totals.raw],
                        ["Harmonized", harmonized.data.totals.harmonized],
                      ].map(([label, value]) => (
                        <div key={String(label)} className="rounded-card border border-line/[0.07] bg-line/[0.02] px-3 py-2">
                          <div className="text-3xs uppercase tracking-[0.1em] text-faint">{label}</div>
                          <div className="mt-1 font-mono text-sm text-ink">{formatCount(Number(value))}</div>
                        </div>
                      ))}
                    </div>
                    <div>
                      <div className="mb-1 flex items-center justify-between text-3xs text-faint">
                        <span>raw</span>
                        <span>
                          {(harmonized.data.totals.reduction_ratio * 100).toFixed(1)}% cross-sensor duplicates
                        </span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-line/[0.06]">
                        <div
                          className="h-full rounded-full bg-accent/70"
                          style={{
                            width: `${
                              harmonized.data.totals.raw
                                ? (harmonized.data.totals.harmonized / harmonized.data.totals.raw) * 100
                                : 0
                            }%`,
                          }}
                        />
                      </div>
                    </div>
                    <p className="text-3xs font-light leading-relaxed text-faint">
                      {harmonized.data.coverage.days_with_matches} of {harmonized.data.coverage.days} days
                      have associations. {harmonized.data.notes[harmonized.data.notes.length - 1]}
                    </p>
                  </div>
                ) : null}
              </Panel>

              <Panel title="Algorithm runs" subtitle="Audit trail for each pass." bodyClassName="p-0">
                <ul>
                  {(runs.data ?? []).slice(0, 5).map((run) => (
                    <li
                      key={run.id}
                      className="flex items-center justify-between gap-3 border-b border-line/[0.06] px-[22px] py-[8px] last:border-0"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-2xs text-ink">
                            {run.kind === "harmonization" ? "Harmonization" : "Event grouping"}
                          </span>
                          <Badge tone={run.status === "succeeded" ? "ok" : "warn"}>
                            {run.status}
                          </Badge>
                        </div>
                        <div className="mt-[2px] font-mono text-3xs text-faint">
                          {run.algorithm_version}
                          {run.is_synthetic ? " · synthetic scope" : ""}
                        </div>
                      </div>
                      <span className="shrink-0 font-mono text-3xs text-faint">
                        {formatDateTimeUtc(run.completed_at ?? run.started_at)}
                      </span>
                    </li>
                  ))}
                  {(runs.data ?? []).length === 0 ? (
                    <li className="px-[22px] py-6 text-center text-xs font-light text-faint">
                      No algorithm runs recorded.
                    </li>
                  ) : null}
                </ul>
              </Panel>
            </div>
          </div>

          <div className="mt-[12px] flex items-start gap-2.5 rounded-card border border-line/[0.08] bg-line/[0.02] px-[18px] py-[13px]">
            <FlaskConical className="mt-[1px] size-3.5 shrink-0 text-faint" aria-hidden />
            <p className="text-2xs font-light leading-relaxed text-muted">
              <span className="text-ink">Methodology.</span> Associations use{" "}
              <code className="font-mono text-muted">S = wₜ·T + wₛ·G + w_f·F</code> with a 180-minute
              window and a 2 km screening distance by default; weights are renormalised when a
              footprint is unknown. Events are DBSCAN clusters in space and time (1.5 km, 24 h,
              ≥ 2 observations). Both are recomputed from stored observations and keep their
              observation identifiers.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
