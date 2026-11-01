import { useQuery } from "@tanstack/react-query";
import { Download, FileText } from "lucide-react";

import { PageHeader } from "@/components/ui/ModuleStatus";
import { DataRow, Panel, StatTile } from "@/components/ui/Panel";
import { EmptyState } from "@/components/ui/EmptyState";
import { fetchReport, reportExportUrl } from "@/lib/intelligenceApi";
import { formatCount, formatFrp } from "@/lib/format";
import { useModules } from "@/lib/queries";
import { useUiStore } from "@/store/ui";

export function ReportsPage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "reports");

  const report = useQuery({
    queryKey: ["reports", dateRange.start, dateRange.end],
    queryFn: ({ signal }) => fetchReport(dateRange.start, dateRange.end, signal),
    staleTime: 60_000,
    retry: 1,
  });

  const data = report.data;

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / Intelligence"
        title="Reports"
        status={module?.status}
        phase={module?.phase}
        description="A briefing snapshot assembled from stored detections: totals, trend, ranked cells, harmonization and anomalies. Every number is computed, never written."
        actions={
          <div className="flex items-center gap-2">
            <a
              href={reportExportUrl(dateRange.start, dateRange.end, "markdown")}
              download
              className="btn-primary inline-flex items-center gap-1.5 px-3 py-[7px] text-xs"
            >
              <Download className="size-3.5" aria-hidden />
              Markdown
            </a>
            <a
              href={reportExportUrl(dateRange.start, dateRange.end, "json")}
              download
              className="btn-glass inline-flex items-center gap-1.5 px-3 py-[7px] text-xs"
            >
              <Download className="size-3.5" aria-hidden />
              JSON
            </a>
          </div>
        }
      />

      {report.isError ? (
        <Panel title="Report unavailable">
          <p className="text-2xs text-danger">The report could not be generated.</p>
        </Panel>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Detections"
          value={formatCount(data?.headline.detections ?? 0)}
          hint={`${dateRange.start} → ${dateRange.end} (UTC)`}
        />
        <StatTile
          label="Active days"
          value={`${formatCount(data?.headline.active_days ?? 0)} / ${formatCount(
            data?.headline.days ?? 0,
          )}`}
          hint="Days with at least one detection"
          tone="ok"
        />
        <StatTile
          label="FRP sum"
          value={formatFrp(data?.headline.frp_sum_mw ?? 0)}
          hint={`Peak ${formatFrp(data?.headline.frp_max_mw ?? null)}`}
        />
        <StatTile
          label="High confidence"
          value={formatCount(data?.headline.high_confidence ?? 0)}
          hint={`MODIS ${formatCount(data?.headline.modis ?? 0)} · VIIRS ${formatCount(
            data?.headline.viirs ?? 0,
          )}`}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Panel title="Report contents" subtitle="Included in the exported document.">
          {data ? (
            <>
              <DataRow label="Daily series">{data.series.length} days</DataRow>
              <DataRow label="Ranked cells">{data.top_cells.length}</DataRow>
              <DataRow label="Matches (stored)">
                {formatCount(data.harmonization.matches_total)} ·{" "}
                {formatCount(data.harmonization.probable)} probable
              </DataRow>
              <DataRow label="Events (stored)">{formatCount(data.harmonization.events)}</DataRow>
              <DataRow label="Anomalies">
                {data.anomalies.status === "ok"
                  ? `${data.anomalies.flagged.length} flagged`
                  : "insufficient history"}
              </DataRow>
              <DataRow label="Coverage">
                {data.coverage.days_with_detections} of {data.coverage.range_days} days
              </DataRow>
              <p className="mt-3 text-3xs font-light leading-relaxed text-faint">
                {data.notes.join(" ")}
              </p>
            </>
          ) : (
            <p className="text-2xs text-muted">Building the report…</p>
          )}
        </Panel>

        <Panel title="Periods with activity" subtitle="Detections per day in the report.">
          {data && data.series.some((point) => point.detections > 0) ? (
            <ul className="space-y-[4px]">
              {data.series
                .filter((point) => point.detections > 0)
                .map((point) => (
                  <li
                    key={point.date}
                    className="flex items-center justify-between border-b border-line/[0.05] py-[4px] text-2xs last:border-0"
                  >
                    <span className="font-mono text-muted">{point.date}</span>
                    <span className="font-mono text-faint">
                      {formatCount(point.detections)} · {formatFrp(point.frp_sum_mw)}
                    </span>
                  </li>
                ))}
            </ul>
          ) : (
            <EmptyState
              icon={<FileText className="size-4" aria-hidden />}
              title="Nothing to report yet"
              description="No detections were stored for this period. Pick a wider range in the header."
            />
          )}
        </Panel>
      </div>
    </>
  );
}
