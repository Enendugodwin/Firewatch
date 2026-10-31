import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Radar } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { DataRow, Panel, StatTile } from "@/components/ui/Panel";
import { fetchAnomalies, type AnomalySeverity } from "@/lib/analyticsApi";
import { formatCount } from "@/lib/format";
import { useModules } from "@/lib/queries";
import { useUiStore } from "@/store/ui";

const SEVERITY_TONE: Record<AnomalySeverity, "neutral" | "info" | "warn" | "danger"> = {
  normal: "neutral",
  below_baseline: "neutral",
  moderate: "info",
  high: "warn",
  critical: "danger",
  unknown_scale: "warn",
};

const METHOD_STEPS = [
  "For each day, take the median of the preceding baseline window of observed days.",
  "Scale the deviation with 1.4826 × MAD, so one huge day cannot inflate the baseline.",
  "Days without recorded source availability are excluded, never counted as zeros.",
  "Flag a day when the robust z-score reaches the threshold; no history, no claim.",
];

export function AnomaliesPage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "anomalies");

  const anomalies = useQuery({
    queryKey: ["anomalies", dateRange.start, dateRange.end],
    queryFn: ({ signal }) => fetchAnomalies(dateRange.start, dateRange.end, signal),
    staleTime: 60_000,
    retry: 1,
  });

  const data = anomalies.data;
  const insufficient = data?.status === "insufficient_history";

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / Science"
        title="Anomaly Detection"
        status={module?.status}
        phase={module?.phase}
        description="Days whose detection count departs from their own recent history, scored with a robust z-score. When there is not enough history the engine says so instead of inventing anomalies."
      />

      {anomalies.isError ? (
        <Panel title="Anomaly engine unavailable">
          <p className="text-2xs text-danger">The anomaly endpoint could not be reached.</p>
        </Panel>
      ) : null}

      {anomalies.isLoading ? (
        <Panel title="Scoring">
          <p className="text-2xs text-muted">Loading the baseline…</p>
        </Panel>
      ) : null}

      {insufficient && data ? (
        <Panel
          title="Not enough history for a baseline"
          subtitle="An anomaly is only meaningful relative to a baseline; this scope does not have one yet."
          actions={<Badge tone="warn">insufficient history</Badge>}
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-[2px] size-4 shrink-0 text-warn" aria-hidden />
              <div className="space-y-2 text-2xs font-light leading-relaxed text-muted">
                <p>{data.requirements.note}</p>
                <p>
                  <span className="text-ink">{data.requirements.available_days}</span> observed
                  baseline days are available;{" "}
                  <span className="text-ink">{data.requirements.needed_days}</span> are required for
                  the default {data.method.baseline_days}-day window.
                </p>
                <p>
                  To enable this workspace, ingest more history for the same scope (region and
                  sensor). The engine needs days a source actually observed — gaps do not count.
                </p>
              </div>
            </div>
          </div>
        </Panel>
      ) : null}

      {data && !insufficient && data.method.baseline_source === "within_window" ? (
        <div className="mb-4 flex items-start gap-2 rounded-card border border-azure/25 bg-azure/[0.05] px-[14px] py-[10px]">
          <Radar className="mt-[1px] size-3.5 shrink-0 text-azure" aria-hidden />
          <p className="text-2xs font-light leading-relaxed text-muted">
            <span className="text-ink">Short-history baseline.</span> There are not yet enough
            earlier days for a preceding-history baseline, so each day is compared with the other
            observed days in this window. Treat these flags as provisional; ingesting more days
            switches the engine to the stronger baseline automatically.
          </p>
        </div>
      ) : null}

      {data && !insufficient ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile
              label="Anomalies"
              value={formatCount(data.anomalies.length)}
              hint={`Scored ${formatCount(data.evaluated_days)} day(s)`}
              tone={data.anomalies.length > 0 ? "warn" : "ok"}
            />
            <StatTile
              label="Baseline median"
              value={formatCount(data.baseline?.median ?? 0)}
              hint={`Median of ${formatCount(data.baseline?.days ?? 0)} observed days`}
            />
            <StatTile
              label="Robust scale"
              value={formatCount(data.baseline?.scale ?? 0)}
              hint="1.4826 × MAD of the baseline"
            />
            <StatTile
              label="Threshold"
              value={`z ≥ ${data.method.z_threshold}`}
              hint={`${data.method.baseline_days}-day window, ${data.method.metric}`}
            />
          </div>

          <Panel
            className="mt-4"
            title="Flagged days"
            subtitle="Positive departures from the baseline, newest first."
          >
            {data.anomalies.length === 0 ? (
              <EmptyState
                icon={<Radar className="size-4" aria-hidden />}
                title="No anomalies in this period"
                description="Every scored day stayed within the threshold of its baseline."
              />
            ) : (
              <ul className="space-y-[8px]">
                {[...data.anomalies].reverse().map((point) => (
                  <li
                    key={point.date}
                    className="rounded-card border border-line/[0.08] bg-line/[0.02] px-[14px] py-[10px]"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-ink">{point.date}</span>
                      <Badge tone={SEVERITY_TONE[point.severity]}>{point.severity}</Badge>
                      <span className="font-mono text-3xs text-faint">
                        z {point.robust_z ?? "n/a"}
                      </span>
                      <span className="ml-auto font-mono text-3xs text-muted">
                        {formatCount(point.observed)} observed · {formatCount(point.expected)}{" "}
                        expected
                      </span>
                    </div>
                    {point.explanation ? (
                      <p className="mt-[6px] text-2xs font-light leading-relaxed text-muted">
                        {point.explanation}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </>
      ) : null}

      <Panel className="mt-4" title="Method" subtitle={data ? data.method.version : undefined}>
        <div className="grid gap-4 sm:grid-cols-2">
          <ol className="space-y-[6px] text-2xs font-light leading-relaxed text-muted">
            {METHOD_STEPS.map((step, index) => (
              <li key={step} className="flex gap-2">
                <span className="font-mono text-3xs text-faint">{index + 1}.</span>
                {step}
              </li>
            ))}
          </ol>
          <div>
            {data ? (
              <>
                <DataRow label="Method">{data.method.name}</DataRow>
                <DataRow label="Baseline window">{data.method.baseline_days} days</DataRow>
                <DataRow label="Minimum baseline">{data.method.min_baseline_days} days</DataRow>
                <DataRow label="Comparison">{data.method.comparison}</DataRow>
                <DataRow label="Metric">{data.method.metric}</DataRow>
              </>
            ) : (
              <p className="text-2xs text-muted">Loading method…</p>
            )}
          </div>
        </div>
        {data ? (
          <p className="mt-3 border-t border-line/[0.07] pt-[9px] text-3xs font-light leading-relaxed text-faint">
            {data.notes.join(" ")}
          </p>
        ) : null}
      </Panel>
    </>
  );
}
