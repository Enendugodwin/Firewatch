import { Cloud, Database, HardDrive, RefreshCw, ShieldCheck, Upload } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { DataRow, Panel, StatTile } from "@/components/ui/Panel";
import { formatCount } from "@/lib/format";
import {
  formatBytes,
  useDatasets,
  useInfrastructure,
  useSyncActions,
} from "@/lib/infrastructureApi";
import { useModules } from "@/lib/queries";
import { useUiStore } from "@/store/ui";

const MODE_TONE = { local: "ok", hybrid: "info", cloud: "warn" } as const;

export function CloudReadinessPage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "cloud-readiness");

  const status = useInfrastructure();
  const datasets = useDatasets();
  const { exportRun, preview, sync, test } = useSyncActions();

  const data = status.data;
  const storage = data?.storage;
  const inventory = datasets.data;
  const mode = (data?.deployment_mode ?? "local") as "local" | "hybrid" | "cloud";

  const used = storage?.used_bytes ?? 0;
  const allocation = storage?.allocation_bytes ?? 0;
  const usedShare = allocation > 0 ? (used / allocation) * 100 : 0;

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / Infrastructure"
        title="Cloud Readiness"
        status={module?.status}
        phase={module?.phase}
        description="Deployment mode, storage, dataset inventory and the path to Cloudflare R2. Local mode needs no cloud credentials; nothing is uploaded until you ask for it."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => test.mutate()}
              className="btn-glass inline-flex items-center gap-1.5 px-3 py-[6px] text-2xs"
            >
              <ShieldCheck className="size-3" aria-hidden />
              Test storage
            </button>
            <button
              type="button"
              onClick={() => exportRun.mutate({ startDate: dateRange.start, endDate: dateRange.end })}
              disabled={exportRun.isPending}
              className="btn-glass inline-flex items-center gap-1.5 px-3 py-[6px] text-2xs disabled:opacity-40"
            >
              <HardDrive className="size-3" aria-hidden />
              {exportRun.isPending ? "Exporting…" : "Export Parquet"}
            </button>
            <button
              type="button"
              onClick={() => preview.mutate()}
              disabled={preview.isPending}
              className="btn-glass inline-flex items-center gap-1.5 px-3 py-[6px] text-2xs disabled:opacity-40"
            >
              <Cloud className="size-3" aria-hidden />
              Preview sync
            </button>
            <button
              type="button"
              onClick={() => sync.mutate()}
              disabled={sync.isPending}
              className="btn-primary inline-flex items-center gap-1.5 px-3 py-[6px] text-2xs disabled:opacity-40"
            >
              <Upload className="size-3" aria-hidden />
              {sync.isPending ? "Syncing…" : "Synchronise"}
            </button>
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Deployment mode"
          value={mode}
          hint={`storage: ${storage?.mode ?? "—"} · database: ${data?.database_mode ?? "—"}`}
          tone={MODE_TONE[mode]}
        />
        <StatTile
          label="Dataset storage"
          value={formatBytes(used)}
          hint={
            allocation > 0
              ? `${usedShare.toFixed(1)}% of ${formatBytes(allocation)} allocation`
              : "local filesystem"
          }
        />
        <StatTile
          label="PostgreSQL"
          value={formatBytes(data?.database.size_bytes ?? 0)}
          hint={`${data?.database.tables ?? 0} tables · ${data?.database.dialect ?? ""}`}
        />
        <StatTile
          label="Parquet datasets"
          value={formatCount(inventory?.count ?? 0)}
          hint={`${formatBytes(inventory?.total_bytes ?? 0)} · ${formatCount(
            inventory?.records ?? 0,
          )} records`}
        />
      </div>

      {test.data ? (
        <div className="mt-4 rounded-card border border-accent/20 bg-accent/[0.04] px-4 py-3 text-2xs text-muted">
          Storage check: <span className="text-ink">{JSON.stringify(test.data)}</span>
        </div>
      ) : null}

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Panel
          title="Datasets"
          subtitle={inventory ? `root: ${inventory.root}` : "Scanning…"}
          actions={
            <button
              type="button"
              onClick={() => datasets.refetch()}
              className="btn-glass inline-flex items-center gap-1.5 px-2.5 py-[4px] text-3xs"
            >
              <RefreshCw className="size-3" aria-hidden />
              Refresh
            </button>
          }
        >
          {inventory && inventory.datasets.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[38rem] border-collapse text-3xs">
                <thead>
                  <tr className="border-b border-line/[0.08] text-left uppercase tracking-[0.1em] text-faint">
                    <th className="py-[6px] pr-3 font-medium">Dataset</th>
                    <th className="py-[6px] pr-3 font-medium">Coverage</th>
                    <th className="py-[6px] pr-3 text-right font-medium">Records</th>
                    <th className="py-[6px] pr-3 text-right font-medium">Size</th>
                    <th className="py-[6px] font-medium">SHA-256</th>
                  </tr>
                </thead>
                <tbody>
                  {inventory.datasets.map((entry) => (
                    <tr key={entry.dataset} className="border-b border-line/[0.05] text-muted">
                      <td className="py-[6px] pr-3 text-ink">{entry.dataset}</td>
                      <td className="py-[6px] pr-3 font-mono">
                        {entry.coverage_start} → {entry.coverage_end}
                      </td>
                      <td className="py-[6px] pr-3 text-right font-mono">
                        {formatCount(entry.records)}
                      </td>
                      <td className="py-[6px] pr-3 text-right font-mono">
                        {formatBytes(entry.size_bytes)}
                      </td>
                      <td className="py-[6px] font-mono text-faint">{entry.checksum.slice(0, 12)}…</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-2xs text-muted">
              No Parquet datasets yet. Use <span className="text-ink">Export Parquet</span> for the
              header period.
            </p>
          )}
        </Panel>

        <Panel title="Deployment" subtitle="Local, hybrid or cloud — one configuration switch.">
          <DataRow label="Provider">
            {storage?.provider ?? storage?.mode ?? "—"}
            {storage?.r2_configured ? " · R2 configured" : " · no cloud credentials"}
          </DataRow>
          <DataRow label="Local data">
            <span className="font-mono">{storage?.local_directory}</span>
          </DataRow>
          <DataRow label="Free space">{formatBytes(storage?.free_bytes ?? null)}</DataRow>
          <DataRow label="Allocation">{formatBytes(allocation)}</DataRow>
          <DataRow label="Rollups">
            {data?.rollups.available
              ? `${formatCount(data.rollups.rows ?? 0)} rows`
              : "not available"}
          </DataRow>
          <DataRow label="Cloud database">
            {data?.database.cloud_database_configured ? "configured" : "not configured"}
          </DataRow>
          <p className="mt-3 text-3xs font-light leading-relaxed text-faint">
            Uploads are verified by size and SHA-256 before they are recorded. Nothing local is
            deleted by a sync, and an operation is blocked rather than exceeding the allocation.
          </p>
        </Panel>
      </div>

      {preview.data ? (
        <Panel className="mt-4" title="Sync preview" subtitle={`planned ${preview.data.previewed_at}`}>
          <div className="flex flex-wrap gap-3 text-2xs">
            {Object.entries(preview.data.counts).map(([key, value]) => (
              <span key={key} className="inline-flex items-center gap-1.5">
                <Badge tone={key === "matched" ? "ok" : key === "missing" ? "info" : "warn"}>
                  {key}
                </Badge>
                {formatCount(value)}
              </span>
            ))}
            <span className="font-mono text-faint">
              upload {formatBytes(preview.data.upload_bytes)}
            </span>
          </div>
        </Panel>
      ) : null}

      {sync.data ? (
        <Panel className="mt-4" title="Sync report" subtitle={sync.data.status}>
          <DataRow label="Uploaded">{formatCount(sync.data.uploaded ?? 0)}</DataRow>
          <DataRow label="Skipped (already present)">{formatCount(sync.data.skipped ?? 0)}</DataRow>
          <DataRow label="Failed">{formatCount(sync.data.failed ?? 0)}</DataRow>
          <DataRow label="Verified">{formatCount(sync.data.verified ?? 0)}</DataRow>
          {sync.data.reason ? (
            <p className="mt-2 text-2xs text-warn">
              {sync.data.reason}: {sync.data.detail}
            </p>
          ) : null}
        </Panel>
      ) : null}

      {status.isError ? (
        <Panel className="mt-4" title="Infrastructure unavailable">
          <p className="text-2xs text-danger">The infrastructure API could not be reached.</p>
        </Panel>
      ) : null}

      {exportRun.data ? (
        <p className="mt-4 text-3xs text-faint">
          <Database className="mr-1 inline size-3" aria-hidden />
          Exported {exportRun.data.written} file(s) ·{" "}
          {formatCount(exportRun.data.manifest.record_count ?? 0)} records.
        </p>
      ) : null}
    </>
  );
}
