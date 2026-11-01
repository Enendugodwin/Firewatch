import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Globe2, Play, Radar } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge, type Tone } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingBlock, LoadingCue } from "@/components/ui/LoadingCue";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel, StatTile } from "@/components/ui/Panel";
import { formatCount, formatFrp } from "@/lib/format";
import { fetchRegions } from "@/lib/intelligenceApi";
import {
  type AnomaliesReport,
  type GeographicRegion,
  type NotAnalyzed,
  type RegionalSensor,
  type SeasonalityReport,
  type SensorComparison,
  type SpatialReport,
  type TrendsReport,
  analyzeRegion,
  fetchRegionAnomalies,
  fetchRegionCatalog,
  fetchRegionMonthly,
  fetchRegionOverview,
  fetchRegionSeasonality,
  fetchRegionSensors,
  fetchRegionSpatial,
  fetchRegionTrends,
  fetchRegionYearly,
  regionExportUrl,
} from "@/lib/regionalApi";
import { useModules } from "@/lib/queries";
import { useUiStore } from "@/store/ui";

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function isAnalyzed<T extends { status: string }>(value: T | NotAnalyzed | undefined): value is T {
  return Boolean(value && value.status !== "not_analyzed");
}

function trendTone(direction: string): Tone {
  if (direction === "significant_increase") return "fire";
  if (direction === "significant_decrease") return "info";
  return "neutral";
}

function severityTone(severity: string): Tone {
  if (severity === "critical") return "danger";
  if (severity === "high") return "warn";
  if (severity === "moderate") return "info";
  return "neutral";
}

function monthLabel(month: number): string {
  return MONTHS[month - 1] ?? String(month);
}

export function RegionsPage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "regions");
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sensor, setSensor] = useState<RegionalSensor>("ALL");

  const catalog = useQuery({
    queryKey: ["region-catalog"],
    queryFn: ({ signal }) => fetchRegionCatalog(signal),
    staleTime: 10 * 60_000,
    retry: 1,
  });

  const region: GeographicRegion | undefined = useMemo(() => {
    const regions = catalog.data?.regions ?? [];
    return regions.find((item) => item.id === selectedId) ?? regions[0];
  }, [catalog.data, selectedId]);

  const activeId = region?.id ?? null;
  const start = dateRange.start;
  const end = dateRange.end;

  const overview = useQuery({
    queryKey: ["region", activeId, "overview", start, end, sensor],
    queryFn: ({ signal }) => fetchRegionOverview(activeId!, start, end, sensor, signal),
    enabled: Boolean(activeId),
    staleTime: 60_000,
    retry: 1,
  });
  const monthly = useQuery({
    queryKey: ["region", activeId, "monthly", start, end, sensor],
    queryFn: ({ signal }) => fetchRegionMonthly(activeId!, start, end, sensor, signal),
    enabled: Boolean(activeId),
    staleTime: 60_000,
    retry: 1,
  });
  const yearly = useQuery({
    queryKey: ["region", activeId, "yearly", start, end, sensor],
    queryFn: ({ signal }) => fetchRegionYearly(activeId!, start, end, sensor, signal),
    enabled: Boolean(activeId),
    staleTime: 60_000,
    retry: 1,
  });
  const seasonality = useQuery({
    queryKey: ["region", activeId, "seasonality", start, end, sensor],
    queryFn: ({ signal }) => fetchRegionSeasonality(activeId!, start, end, sensor, signal),
    enabled: Boolean(activeId),
    staleTime: 120_000,
    retry: 1,
  });
  const trends = useQuery({
    queryKey: ["region", activeId, "trends", start, end, sensor],
    queryFn: ({ signal }) => fetchRegionTrends(activeId!, start, end, sensor, signal),
    enabled: Boolean(activeId),
    staleTime: 120_000,
    retry: 1,
  });
  const anomalies = useQuery({
    queryKey: ["region", activeId, "anomalies", start, end, sensor],
    queryFn: ({ signal }) => fetchRegionAnomalies(activeId!, start, end, sensor, signal),
    enabled: Boolean(activeId),
    staleTime: 120_000,
    retry: 1,
  });
  const spatial = useQuery({
    queryKey: ["region", activeId, "spatial"],
    queryFn: ({ signal }) => fetchRegionSpatial(activeId!, signal),
    enabled: Boolean(activeId),
    staleTime: 120_000,
    retry: 1,
  });
  const sensors = useQuery({
    queryKey: ["region", activeId, "sensors", start, end],
    queryFn: ({ signal }) => fetchRegionSensors(activeId!, start, end, signal),
    enabled: Boolean(activeId),
    staleTime: 120_000,
    retry: 1,
  });

  const analyze = useMutation({
    mutationFn: () =>
      analyzeRegion(activeId!, { start_date: start, end_date: end, synthetic: false }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["region", activeId] });
      queryClient.invalidateQueries({ queryKey: ["regions"] });
    },
  });

  const ranking = useQuery({
    queryKey: ["regions", start, end],
    queryFn: ({ signal }) => fetchRegions(start, end, signal),
    staleTime: 60_000,
    retry: 1,
  });

  const overviewRaw = overview.data;
  const overviewData = isAnalyzed(overviewRaw) ? overviewRaw : null;
  const analyzed = Boolean(overviewData);
  const season = isAnalyzed(seasonality.data as SeasonalityReport | NotAnalyzed | undefined)
    ? (seasonality.data as SeasonalityReport)
    : null;
  const trend = isAnalyzed(trends.data as TrendsReport | NotAnalyzed | undefined)
    ? (trends.data as TrendsReport)
    : null;
  const anomalyData = isAnalyzed(anomalies.data as AnomaliesReport | NotAnalyzed | undefined)
    ? (anomalies.data as AnomaliesReport)
    : null;
  const spatialData = spatial.data?.status === "ok" ? (spatial.data as SpatialReport) : null;
  const sensorData =
    sensors.data?.status === "ok" || sensors.data?.status === "single_sensor"
      ? (sensors.data as SensorComparison)
      : null;

  const monthlyRows = monthly.data && monthly.data.status === "ok" ? monthly.data.months : [];
  const yearlyRows = yearly.data && yearly.data.status === "ok" ? yearly.data.years : [];

  const heatmap = useMemo(() => {
    const values = new Map<string, number>();
    for (const row of monthlyRows) values.set(`${row.year}-${row.month}`, row.detections);
    const years = [...new Set(monthlyRows.map((row) => row.year))].sort();
    const max = Math.max(0, ...monthlyRows.map((row) => row.detections));
    return { values, years, max };
  }, [monthlyRows]);

  const maxSeasonMean = Math.max(
    1,
    ...(season?.months ?? []).map((month) => month.mean ?? 0),
  );

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / Intelligence"
        title="Regional Intelligence"
        status={module?.status}
        phase={module?.phase}
        description="Trends, seasonality and anomalies for one boundary. The first analysis pass writes regional statistics; every reload reads those, never the 11 million observations."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex items-center gap-2 text-3xs uppercase tracking-[0.12em] text-faint">
              Region
              <select
                value={region?.id ?? ""}
                onChange={(event) => setSelectedId(event.target.value)}
                className="max-w-[16rem] rounded-control border border-line/10 bg-canvas/70 px-2 py-[5px] text-3xs text-ink"
              >
                {(catalog.data?.regions ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                    {item.is_approximate ? " (approx.)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="inline-flex items-center gap-2 text-3xs uppercase tracking-[0.12em] text-faint">
              Sensor
              <select
                value={sensor}
                onChange={(event) => setSensor(event.target.value as RegionalSensor)}
                className="rounded-control border border-line/10 bg-canvas/70 px-2 py-[5px] font-mono text-3xs text-ink"
              >
                <option value="ALL">All</option>
                <option value="MODIS">MODIS</option>
                <option value="VIIRS">VIIRS</option>
              </select>
            </label>
            <button
              type="button"
              onClick={() => analyze.mutate()}
              disabled={!activeId || analyze.isPending}
              className="inline-flex items-center gap-1.5 rounded-full border border-accent/30 px-3 py-[5px] text-3xs uppercase tracking-[0.1em] text-accent transition-colors hover:bg-accent/[0.08] disabled:opacity-40"
            >
              <Play className="size-3" aria-hidden />
              {analyze.isPending ? "Analysing…" : "Analyse period"}
            </button>
            {analyzed && activeId ? (
              <a
                href={regionExportUrl(activeId, start, end, sensor)}
                className="inline-flex items-center gap-1.5 rounded-full border border-line/15 px-3 py-[5px] text-3xs uppercase tracking-[0.1em] text-muted transition-colors hover:text-ink"
              >
                <Download className="size-3" aria-hidden />
                CSV
              </a>
            ) : null}
          </div>
        }
      />

      <p className="mb-3 text-3xs font-light text-faint">
        Period {start} → {end} (UTC, from the header).{" "}
        {region?.is_approximate
          ? "This gazetteer region is an approximate box; import a GeoJSON boundary for exact counts."
          : "Counts use the stored polygon, not its bounding box."}
      </p>

      {catalog.isLoading ? (
        <Panel title="Regions">
          <LoadingBlock label="Loading region catalogue…" lines={3} />
        </Panel>
      ) : !region ? (
        <EmptyState
          icon={<Globe2 className="size-4" aria-hidden />}
          title="No regions available"
          description="The region catalogue is empty. Run the migrations to seed the gazetteer."
        />
      ) : (
        <>
          {analyze.isError ? (
            <Panel className="mb-3" title="Analysis failed">
              <p className="text-2xs text-danger">
                {(analyze.error as Error).message || "The analysis run failed."}
              </p>
            </Panel>
          ) : null}

          {overview.isLoading ? (
            <Panel title="Regional overview">
              <LoadingBlock label="Reading regional statistics…" lines={4} />
            </Panel>
          ) : !overviewData ? (
            <Panel
              title="Regional overview"
              subtitle={`${region.name} · ${region.level}${region.is_approximate ? " · approximate boundary" : ""}`}
            >
              <div className="flex items-start gap-2 text-2xs font-light leading-relaxed text-muted">
                <Radar className="mt-[2px] size-3.5 shrink-0 text-faint" aria-hidden />
                <div>
                  <p>
                    No statistics are stored for this region and period yet. Nothing is
                    estimated: run the analysis to compute them from the observations.
                  </p>
                  <p className="mt-1 text-faint">
                    {(overviewRaw as NotAnalyzed | undefined)?.requirements?.note}
                  </p>
                </div>
              </div>
            </Panel>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatTile
                  label="Detections in region"
                  value={formatCount(overviewData!.totals.detections)}
                  hint={`${formatCount(overviewData!.totals.active_days)} active of ${formatCount(
                    overviewData!.totals.covered_days,
                  )} covered days`}
                />
                <StatTile
                  label="Coverage"
                  value={`${Math.round(overviewData!.totals.coverage * 100)}%`}
                  hint="Analysed/observed days, not zero-filled"
                  tone={overviewData!.totals.coverage < 0.8 ? "warn" : "ok"}
                />
                <StatTile
                  label="Peak month"
                  value={
                    overviewData!.peak_month
                      ? monthLabel(overviewData!.peak_month.month)
                      : "—"
                  }
                  hint={
                    overviewData!.peak_month
                      ? `${formatCount(overviewData!.peak_month.mean_detections)} mean detections`
                      : "Not enough years for a climatology"
                  }
                />
                <StatTile
                  label="Detected anomalies"
                  value={formatCount(overviewData!.anomalies.count)}
                  hint={
                    overviewData!.anomalies.status === "ok"
                      ? `${overviewData!.anomalies.evaluated_months} months evaluated`
                      : "No same-month baseline yet"
                  }
                  tone={overviewData!.anomalies.count > 0 ? "warn" : "neutral"}
                />
              </div>

              <Panel
                className="mt-4"
                title="Monthly seasonality"
                subtitle="Mean of yearly monthly means; a month needs two years of coverage."
                actions={
                  season ? (
                    <Badge
                      tone={
                        season.status === "ok"
                          ? "ok"
                          : season.status === "partial"
                            ? "warn"
                            : "neutral"
                      }
                    >
                      {season.status.replace("_", " ")}
                    </Badge>
                  ) : null
                }
              >
                {seasonality.isLoading ? (
                  <LoadingBlock label="Computing seasonal profile…" lines={3} />
                ) : season ? (
                  <>
                    <div className="flex items-end gap-1" role="img" aria-label="Monthly seasonal profile">
                      {season.months.map((month) => (
                        <div key={month.month} className="flex min-w-0 flex-1 flex-col items-center gap-1">
                          <div className="flex h-[84px] w-full items-end">
                            <div
                              title={`${monthLabel(month.month)}: ${
                                month.mean === null ? "no coverage" : `${month.mean.toFixed(1)} mean`
                              } · ${month.years} year(s)`}
                              className={
                                month.sufficient
                                  ? "w-full rounded-t-[2px] bg-accent/60"
                                  : "w-full rounded-t-[2px] border border-dashed border-line/25 bg-line/[0.03]"
                              }
                              style={{
                                height: `${Math.max(
                                  4,
                                  ((month.mean ?? 0) / maxSeasonMean) * 100,
                                )}%`,
                              }}
                            />
                          </div>
                          <span className="text-[9px] uppercase tracking-[0.06em] text-faint">
                            {monthLabel(month.month)}
                          </span>
                        </div>
                      ))}
                    </div>
                    <p className="mt-2 text-2xs font-light text-muted">
                      {season.peak_month
                        ? `Peak ${monthLabel(season.peak_month)}${
                            season.trough_month ? ` · trough ${monthLabel(season.trough_month)}` : ""
                          }${season.seasonal_amplitude ? ` · amplitude ${season.seasonal_amplitude.toFixed(1)}×` : ""}`
                        : season.requirements.note}
                    </p>
                  </>
                ) : null}
              </Panel>

              <Panel
                className="mt-4"
                title="Year × month heatmap"
                subtitle="Each cell is that month's detection count; dashed cells have no analysed coverage."
              >
                {monthly.isLoading ? (
                  <LoadingBlock label="Loading monthly statistics…" lines={3} />
                ) : heatmap.years.length === 0 ? (
                  <p className="text-2xs text-muted">No monthly statistics for this window.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[40rem] border-collapse text-3xs">
                      <thead>
                        <tr className="text-faint">
                          <th className="py-1 pr-2 text-left font-medium">Year</th>
                          {MONTHS.map((month) => (
                            <th key={month} className="px-1 py-1 text-center font-medium">
                              {month}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {heatmap.years.map((year) => (
                          <tr key={year}>
                            <td className="py-1 pr-2 font-mono text-muted">{year}</td>
                            {MONTHS.map((month, index) => {
                              const value = heatmap.values.get(`${year}-${index + 1}`);
                              const intensity =
                                value === undefined || heatmap.max === 0
                                  ? 0
                                  : Math.sqrt(value / heatmap.max);
                              return (
                                <td key={month} className="px-1 py-1">
                                  <div
                                    title={
                                      value === undefined
                                        ? `${year}-${index + 1}: no coverage`
                                        : `${year}-${index + 1}: ${value.toLocaleString("en-US")} detections`
                                    }
                                    className={
                                      value === undefined
                                        ? "h-6 rounded-[2px] border border-dashed border-line/20"
                                        : "h-6 rounded-[2px] border border-line/10"
                                    }
                                    style={
                                      value === undefined
                                        ? undefined
                                        : {
                                            backgroundColor: `rgba(239, 68, 68, ${0.12 + intensity * 0.78})`,
                                          }
                                    }
                                  />
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>

              <Panel
                className="mt-4"
                title="Long-term trend"
                subtitle="Mann–Kendall on complete years, with Sen's slope."
                actions={
                  trend ? (
                    <div className="flex items-center gap-2">
                      {trend.status !== "ok" ? (
                        <Badge tone="warn">{trend.status.replaceAll("_", " ")}</Badge>
                      ) : null}
                      <Badge tone={trendTone(trend.mann_kendall.trend)}>
                        {trend.mann_kendall.trend.replaceAll("_", " ")}
                      </Badge>
                    </div>
                  ) : null
                }
              >
                {trends.isLoading ? (
                  <LoadingBlock label="Running the trend test…" lines={3} />
                ) : trend ? (
                  <>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="rounded-card border border-line/[0.07] bg-line/[0.02] px-3 py-2">
                        <div className="text-3xs uppercase tracking-[0.1em] text-faint">p-value</div>
                        <div className="mt-1 font-mono text-sm text-ink">
                          {trend.mann_kendall.p_value === null
                            ? "—"
                            : trend.mann_kendall.p_value.toFixed(3)}
                        </div>
                      </div>
                      <div className="rounded-card border border-line/[0.07] bg-line/[0.02] px-3 py-2">
                        <div className="text-3xs uppercase tracking-[0.1em] text-faint">
                          Sen's slope / year
                        </div>
                        <div className="mt-1 font-mono text-sm text-ink">
                          {trend.mann_kendall.sen_slope_per_year === null
                            ? "—"
                            : `${trend.mann_kendall.sen_slope_per_year >= 0 ? "+" : ""}${trend.mann_kendall.sen_slope_per_year.toFixed(1)}`}
                        </div>
                      </div>
                      <div className="rounded-card border border-line/[0.07] bg-line/[0.02] px-3 py-2">
                        <div className="text-3xs uppercase tracking-[0.1em] text-faint">
                          Complete years
                        </div>
                        <div className="mt-1 font-mono text-sm text-ink">
                          {trend.requirements.available_complete_years} / {trend.requirements.needed_years}
                        </div>
                      </div>
                    </div>

                    {yearlyRows.length > 0 ? (
                      <ul className="mt-3 space-y-1">
                        {yearlyRows.map((year) => (
                          <li
                            key={year.year}
                            className="flex items-center justify-between gap-3 border-b border-line/[0.05] py-1 text-2xs"
                          >
                            <span className="font-mono text-muted">
                              {year.year}
                              {year.complete ? "" : " (partial)"}
                            </span>
                            <span className="font-mono text-ink">{formatCount(year.detections)}</span>
                            <span
                              className={
                                year.yoy_change === null
                                  ? "text-faint"
                                  : year.yoy_change >= 0
                                    ? "text-accent"
                                    : "text-azure"
                              }
                            >
                              {year.yoy_change === null
                                ? "—"
                                : `${year.yoy_change >= 0 ? "+" : ""}${(year.yoy_change * 100).toFixed(1)}%`}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : null}

                    <p className="mt-2 text-3xs font-light leading-relaxed text-faint">
                      {trend.requirements.note}
                    </p>
                  </>
                ) : null}
              </Panel>

              <div className="mt-4 grid gap-3 xl:grid-cols-2">
                <Panel
                  title="Anomalies"
                  subtitle="Each month compared with the same calendar month in other years."
                >
                  {anomalies.isLoading ? (
                    <LoadingBlock label="Checking the same-month baseline…" lines={3} />
                  ) : anomalyData ? (
                    anomalyData.count === 0 ? (
                      <p className="text-2xs font-light text-muted">
                        {anomalyData.requirements.note}
                      </p>
                    ) : (
                      <ul className="space-y-1.5">
                        {anomalyData.anomalies.map((item) => (
                          <li
                            key={item.period}
                            className="flex items-start justify-between gap-3 rounded-card border border-line/[0.07] px-3 py-2"
                          >
                            <span>
                              <span className="font-mono text-3xs text-ink">{item.period}</span>
                              <span className="ml-2 text-2xs font-light text-muted">
                                {formatCount(item.observed)} vs {formatCount(item.expected_median)}
                                {item.deviation_ratio === null
                                  ? ""
                                  : ` (${item.deviation_ratio >= 0 ? "+" : ""}${(item.deviation_ratio * 100).toFixed(1)}%)`}
                              </span>
                            </span>
                            <Badge tone={severityTone(item.severity)}>{item.severity}</Badge>
                          </li>
                        ))}
                      </ul>
                    )
                  ) : null}
                </Panel>

                <Panel
                  title="Sensor comparison"
                  subtitle="MODIS and VIIRS are reported separately; levels are not interchangeable."
                >
                  {sensors.isLoading ? (
                    <LoadingBlock label="Comparing sensors…" lines={2} />
                  ) : sensorData ? (
                    <>
                      <div className="space-y-1">
                        {Object.entries(sensorData.sensors).map(([name, totals]) => (
                          <div
                            key={name}
                            className="flex items-center justify-between border-b border-line/[0.05] py-1 text-2xs"
                          >
                            <span className="font-mono text-muted">{name}</span>
                            <span className="font-mono text-ink">
                              {formatCount(totals.detections)}
                            </span>
                            <span className="text-faint">{totals.active_days} active days</span>
                          </div>
                        ))}
                      </div>
                      <p className="mt-2 text-2xs font-light text-muted">
                        {sensorData.correlation
                          ? `Monthly agreement r = ${sensorData.correlation.pearson_r.toFixed(2)} over ${sensorData.correlation.months} months (correlation, not calibrated equivalence).`
                          : sensorData.requirements.note}
                      </p>
                    </>
                  ) : null}
                </Panel>
              </div>

              <Panel
                className="mt-4"
                title="Recurring activity cells"
                subtitle={`${region.grid_degrees}° screening grid inside the boundary — not an H3 index.`}
              >
                {spatial.isLoading ? (
                  <LoadingBlock label="Loading spatial summary…" lines={3} />
                ) : spatialData && spatialData.cells.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[34rem] border-collapse text-3xs">
                      <thead>
                        <tr className="border-b border-line/[0.08] text-left uppercase tracking-[0.1em] text-faint">
                          <th className="py-[6px] pr-3 font-medium">Cell centre</th>
                          <th className="py-[6px] pr-3 text-right font-medium">Detections</th>
                          <th className="py-[6px] pr-3 text-right font-medium">FRP sum</th>
                          <th className="py-[6px] pr-3 text-right font-medium">Years</th>
                          <th className="py-[6px] text-right font-medium">Recurrence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {spatialData.cells.slice(0, 12).map((cell) => (
                          <tr
                            key={`${cell.lat_index}-${cell.lon_index}`}
                            className="border-b border-line/[0.05] text-muted"
                          >
                            <td className="py-[6px] pr-3 font-mono text-ink">
                              {cell.latitude.toFixed(2)}, {cell.longitude.toFixed(2)}
                            </td>
                            <td className="py-[6px] pr-3 text-right font-mono">
                              {formatCount(cell.detections)}
                            </td>
                            <td className="py-[6px] pr-3 text-right font-mono">
                              {formatFrp(cell.frp_sum_mw)}
                            </td>
                            <td className="py-[6px] pr-3 text-right font-mono">
                              {cell.years_with_detections}
                            </td>
                            <td className="py-[6px] text-right font-mono">
                              {Math.round(cell.recurrence * 100)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-2xs text-muted">
                    {spatialData?.requirements?.note ?? "No spatial summary for this region."}
                  </p>
                )}
              </Panel>

              <p className="mt-3 text-3xs font-light leading-relaxed text-faint">
                {overviewData!.notes.join(" ")} {overviewData!.sensor_note}
              </p>
            </>
          )}
        </>
      )}

      <Panel
        className="mt-4"
        title="Ranked regions (approximate boxes)"
        subtitle="The original gazetteer ranking for the header period; open a row in the engine."
      >
        {ranking.isLoading ? (
          <LoadingCue label="Ranking regions…" />
        ) : ranking.data && ranking.data.regions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] border-collapse text-3xs">
              <thead>
                <tr className="border-b border-line/[0.08] text-left uppercase tracking-[0.1em] text-faint">
                  <th className="py-[6px] pr-3 font-medium">Region</th>
                  <th className="py-[6px] pr-3 font-medium">ISO</th>
                  <th className="py-[6px] pr-3 text-right font-medium">Detections</th>
                  <th className="py-[6px] pr-3 text-right font-medium">Active days</th>
                  <th className="py-[6px] pr-3 text-right font-medium">FRP sum</th>
                  <th className="py-[6px] text-right font-medium">Engine</th>
                </tr>
              </thead>
              <tbody>
                {ranking.data.regions.map((item) => (
                  <tr key={item.name} className="border-b border-line/[0.05] text-muted">
                    <td className="py-[6px] pr-3 text-ink">{item.name}</td>
                    <td className="py-[6px] pr-3 font-mono text-faint">{item.iso ?? "—"}</td>
                    <td className="py-[6px] pr-3 text-right font-mono">
                      {formatCount(item.detections)}
                    </td>
                    <td className="py-[6px] pr-3 text-right font-mono">
                      {formatCount(item.active_days)}
                    </td>
                    <td className="py-[6px] pr-3 text-right font-mono">
                      {formatFrp(item.frp_sum_mw)}
                    </td>
                    <td className="py-[6px] text-right">
                      {item.region_id ? (
                        <button
                          type="button"
                          onClick={() => setSelectedId(item.region_id!)}
                          className="rounded-full border border-line/15 px-2 py-[2px] text-3xs text-faint hover:text-ink"
                        >
                          Open
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-2xs text-muted">No ranked regions for this period.</p>
        )}
        {ranking.data ? (
          <p className="mt-2 text-3xs font-light leading-relaxed text-faint">
            {ranking.data.note}
          </p>
        ) : null}
      </Panel>
    </>
  );
}
