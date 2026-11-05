import { Archive, Download, KeyRound, ShieldAlert, Trash2 } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { DataRow, Panel, StatTile } from "@/components/ui/Panel";
import { API_BASE_URL, getAdminToken, saveAdminToken } from "@/lib/api";
import {
  previewRunDelete,
  useClearFirmsKey,
  useDeleteRun,
  useFirmsKey,
  useIngestionRuns,
  useSaveFirmsKey,
  useTestFirmsKey,
} from "@/lib/adminApi";
import { formatCount } from "@/lib/format";
import { formatBytes } from "@/lib/infrastructureApi";
import {
  useCreateRawExport,
  useDeleteRawExport,
  useRawExports,
  useRawInventory,
  useRunRetention,
} from "@/lib/rawArchiveApi";

const DEFAULT_DAYS = 90;

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function shiftDays(days: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - days);
  return date.toISOString().slice(0, 10);
}

export function RawArchivePage() {
  const inventory = useRawInventory();
  const exports = useRawExports();
  const createExport = useCreateRawExport();
  const deleteExport = useDeleteRawExport();
  const retention = useRunRetention();
  const firmsKey = useFirmsKey();
  const saveKey = useSaveFirmsKey();
  const clearKey = useClearFirmsKey();
  const testKey = useTestFirmsKey();
  const runs = useIngestionRuns();
  const deleteRun = useDeleteRun();

  const [startDate, setStartDate] = useState(shiftDays(DEFAULT_DAYS));
  const [endDate, setEndDate] = useState(shiftDays(10));
  const [notice, setNotice] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [adminToken, setAdminToken] = useState(getAdminToken());
  const [downloading, setDownloading] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const policy = inventory.data?.policy;
  const totals = inventory.data?.totals;
  const days = inventory.data?.days ?? [];

  const runExport = () => {
    setNotice(null);
    createExport.mutate(
      { start_date: startDate, end_date: endDate },
      {
        onSuccess: (record) =>
          setNotice(
            `Exported ${formatCount(record.rows)} payloads (${formatBytes(record.size_bytes)}). Download it, then delete the range.`,
          ),
        onError: (error) => setNotice(error.message),
      },
    );
  };

  const runDelete = (id: string, sha256: string, range: string) => {
    const confirmed = window.confirm(
      `Delete the raw payloads for ${range}? The analysis (calendar, analytics, matches) is unaffected. This cannot be undone.`,
    );
    if (!confirmed) return;
    setNotice(null);
    deleteExport.mutate(
      { id, confirm_sha256: sha256 },
      {
        onSuccess: (result) =>
          setNotice(`Deleted ${formatCount(result.rows_deleted)} raw payloads for ${range}.`),
        onError: (error) => setNotice(error.message),
      },
    );
  };

  const runRetention = () => {
    const confirmed = window.confirm(
      `Delete every raw payload older than ${policy?.retention_days ?? DEFAULT_DAYS} days ` +
        `(before ${policy?.retention_cutoff ?? "the cutoff"})? Analysis stays available.`,
    );
    if (!confirmed) return;
    setNotice(null);
    retention.mutate(
      { days: policy?.retention_days ?? DEFAULT_DAYS },
      {
        onSuccess: (result) =>
          setNotice(
            result.rows_deleted !== undefined
              ? `Retention removed ${formatCount(result.rows_deleted)} raw payloads older than ${result.cutoff}.`
              : `Nothing to remove before ${result.cutoff}.`,
          ),
        onError: (error) => setNotice(error.message),
      },
    );
  };

  const keyState = firmsKey.data;

  const downloadExport = async (id: string, range: string) => {
    setDownloading(id);
    setNotice(null);
    try {
      const token = getAdminToken();
      const response = await fetch(
        `${API_BASE_URL}/api/v1/admin/raw/exports/${id}/download`,
        { headers: token ? { "X-Admin-Token": token } : {} },
      );
      if (!response.ok) {
        throw new Error(`Download failed with status ${response.status}.`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `firewatch-raw-${range.replace(/[^0-9A-Za-z-]/g, "")}.csv.gz`;
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(`Downloaded the raw archive for ${range}.`);
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setDownloading(null);
    }
  };

  const previewAndDeleteRun = async (runId: string, label: string) => {
    setNotice(null);
    try {
      const preview = await previewRunDelete(runId);
      const confirmed = window.confirm(
        `Delete the ingested data for ${label}?\n\n` +
          `${formatCount(preview.observations)} canonical detections, ` +
          `${formatCount(preview.raw_observations)} raw payloads, ` +
          `${formatCount(preview.matches)} matches and ` +
          `${formatCount(preview.partitions)} partitions will be removed. ` +
          `Rollups are rebuilt. This cannot be undone.`,
      );
      if (!confirmed) return;
      const result = await deleteRun.mutateAsync(runId);
      setNotice(
        `Removed ${formatCount(result.observations)} detections from ${label}. The window can be ingested again.`,
      );
    } catch (error) {
      setNotice((error as Error).message);
    }
  };

  const storeAdminToken = () => {
    saveAdminToken(adminToken);
    setNotice(
      adminToken.trim()
        ? "Admin token saved for this browser tab."
        : "Admin token cleared.",
    );
    void queryClient.invalidateQueries();
  };

  const saveFirmsKey = () => {
    setNotice(null);
    saveKey.mutate(apiKey, {
      onSuccess: (state) => {
        setApiKey("");
        setNotice(`FIRMS key saved (${state.masked ?? "configured"}). NASA ingestion can run now.`);
      },
      onError: (error) => setNotice(error.message),
    });
  };

  const clearFirmsKey = () => {
    if (!window.confirm("Remove the stored FIRMS key and fall back to the environment value?")) {
      return;
    }
    setNotice(null);
    clearKey.mutate(undefined, {
      onSuccess: (state) =>
        setNotice(
          state.configured
            ? "Stored key removed; the environment key is still active."
            : "Stored key removed. NASA ingestion is disabled until a key is set.",
        ),
      onError: (error) => setNotice(error.message),
    });
  };

  const testFirmsKey = () => {
    setNotice(null);
    testKey.mutate(undefined, {
      onSuccess: (result) =>
        setNotice(
          `FIRMS accepted the key. MODIS_NRT coverage: ${result.min_date ?? "unknown"} ? ${result.max_date ?? "unknown"}.`,
        ),
      onError: (error) => setNotice(error.message),
    });
  };

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / Administration"
        title="Admin Portal"
        description="Raw payloads are provenance only: exports, downloads and retention live here. Calendar, analytics, matches and reports are computed from the canonical store, so deleting a payload never changes a number on screen."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              onClick={runRetention}
              disabled={retention.isPending || !policy}
            >
              <ShieldAlert className="size-3" aria-hidden />
              {retention.isPending ? "Applying retention…" : "Run retention now"}
            </Button>
          </div>
        }
      />

      {notice ? (
        <div className="mb-4 rounded-card border border-azure/25 bg-azure/[0.06] px-4 py-3 text-xs leading-relaxed text-muted">
          {notice}
        </div>
      ) : null}

      <Panel
        className="mb-3"
        title="Admin access"
        subtitle="Required for every administrative write when the API runs in production. Stored in this tab only; the browser never receives the server's token."
      >
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-1 flex-col gap-1 text-2xs text-faint">
            X-Admin-Token
            <input
              type="password"
              value={adminToken}
              autoComplete="off"
              onChange={(event) => setAdminToken(event.target.value)}
              placeholder="Paste the ADMIN_TOKEN configured on the server"
              className="min-w-[240px] rounded-lg border border-line/10 bg-line/[0.03] px-3 py-2 font-mono text-xs text-ink"
            />
          </label>
          <Button variant="secondary" onClick={storeAdminToken}>
            {adminToken.trim() ? "Save token" : "Clear token"}
          </Button>
        </div>
        <p className="mt-2 text-2xs leading-relaxed text-faint">
          In local development the API allows writes without a token. A production
          deployment with <code>ADMIN_TOKEN</code> unset disables them.{" "}
          <a href="/login" className="text-azure underline decoration-azure/30 underline-offset-2">
            Sign in as an operator
          </a>{" "}
          to use a role-based session instead.
        </p>
      </Panel>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Retained raw payloads"
          value={formatCount(totals?.rows ?? 0)}
          hint={`${formatCount(totals?.days ?? 0)} days with payloads`}
        />
        <StatTile
          label="Payload footprint"
          value={totals?.payload_bytes != null ? formatBytes(totals.payload_bytes) : "—"}
          hint="Excludes canonical rows and indexes"
          tone="info"
        />
        <StatTile
          label="Past retention"
          value={formatCount(totals?.past_retention_rows ?? 0)}
          hint={policy ? `Cutoff ${policy.retention_cutoff}` : "Loading policy"}
          tone={(totals?.past_retention_rows ?? 0) > 0 ? "warn" : "ok"}
        />
        <StatTile
          label="Export age floor"
          value={`${policy?.export_min_age_days ?? 5} days`}
          hint={policy ? `Latest exportable ${policy.export_cutoff}` : "Loading policy"}
        />
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[1.4fr_1fr]">
        <Panel
          title="Export a range"
          subtitle="CSV.GZ with the source row and its original payload. The archive SHA-256 is the key that unlocks deletion for that exact range."
        >
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-2xs text-faint">
              Start
              <input
                type="date"
                value={startDate}
                max={endDate}
                onChange={(event) => setStartDate(event.target.value)}
                className="rounded-lg border border-line/10 bg-line/[0.03] px-3 py-2 text-xs text-ink"
              />
            </label>
            <label className="flex flex-col gap-1 text-2xs text-faint">
              End
              <input
                type="date"
                value={endDate}
                max={policy?.export_cutoff ?? todayIso()}
                onChange={(event) => setEndDate(event.target.value)}
                className="rounded-lg border border-line/10 bg-line/[0.03] px-3 py-2 text-xs text-ink"
              />
            </label>
            <Button variant="primary" onClick={runExport} disabled={createExport.isPending}>
              <Archive className="size-3" aria-hidden />
              {createExport.isPending ? "Exporting…" : "Export CSV.GZ"}
            </Button>
          </div>
          <p className="mt-3 text-2xs leading-relaxed text-faint">
            One request covers at most {policy?.export_max_days ?? 62} days, and only payloads older
            than {policy?.export_min_age_days ?? 5} days are exportable so live ingestion is never
            captured mid-flight.
          </p>
        </Panel>

        <Panel title="Retention policy" subtitle="Automatic raw-payload expiry. Analysis is never part of this job.">
          <DataRow label="Keep raw payloads for">
            {policy?.retention_days ?? DEFAULT_DAYS} days
          </DataRow>
          <DataRow label="Deletes before">{policy?.retention_cutoff ?? "—"}</DataRow>
          <DataRow label="Rows eligible now">
            {formatCount(totals?.past_retention_rows ?? 0)}
          </DataRow>
          <DataRow label="Canonical observations">Untouched</DataRow>
          <p className="mt-3 text-2xs leading-relaxed text-faint">
            Run this from the admin portal or on a schedule:
            <code className="ml-1 rounded bg-line/[0.06] px-1 py-[1px]">
              python -m scripts.retention --apply
            </code>
          </p>
        </Panel>
      </div>

      <Panel
        className="mt-3"
        title="NASA FIRMS MAP_KEY"
        subtitle="Ingestion credential. Stored server-side and applied immediately; the browser only ever sees a masked fingerprint."
      >
        <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
          <div>
            <label className="flex flex-col gap-1 text-2xs text-faint">
              API key
              <div className="flex flex-wrap gap-2">
                <input
                  type="password"
                  value={apiKey}
                  autoComplete="off"
                  spellCheck={false}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={
                    keyState?.configured
                      ? `Replace ${keyState.masked ?? "stored key"}`
                      : "Paste your FIRMS MAP_KEY"
                  }
                  className="min-w-[220px] flex-1 rounded-lg border border-line/10 bg-line/[0.03] px-3 py-2 font-mono text-xs text-ink"
                />
                <Button
                  variant="primary"
                  onClick={saveFirmsKey}
                  disabled={saveKey.isPending || apiKey.trim().length < 8}
                >
                  <KeyRound className="size-3" aria-hidden />
                  {saveKey.isPending ? "Saving?" : "Save key"}
                </Button>
              </div>
            </label>
            <p className="mt-2 text-2xs leading-relaxed text-faint">
              Request a free key from{" "}
              <a
                href="https://firms.modaps.eosdis.nasa.gov/api/map_key/"
                target="_blank"
                rel="noreferrer"
                className="text-azure underline decoration-azure/30 underline-offset-2"
              >
                NASA FIRMS
              </a>
              . The key is never logged, returned or sent to the map.
            </p>
          </div>
          <div>
            <DataRow label="Status">
              {keyState?.configured ? (
                <span className="text-accent">configured</span>
              ) : (
                <span className="text-warn">not configured</span>
              )}
            </DataRow>
            <DataRow label="Source">{keyState?.source ?? "?"}</DataRow>
            <DataRow label="Fingerprint">{keyState?.masked ?? "?"}</DataRow>
            <DataRow label="Updated">
              {keyState?.updated_at
                ? keyState.updated_at.slice(0, 16).replace("T", " ")
                : "?"}
            </DataRow>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button
                variant="secondary"
                onClick={testFirmsKey}
                disabled={testKey.isPending || !keyState?.configured}
              >
                {testKey.isPending ? "Testing?" : "Test key"}
              </Button>
              <Button
                variant="danger"
                onClick={clearFirmsKey}
                disabled={clearKey.isPending || !keyState?.configured}
              >
                <Trash2 className="size-3" aria-hidden />
                Remove
              </Button>
            </div>
          </div>
        </div>
      </Panel>

      <Panel
        className="mt-3"
        title="Ingested data"
        subtitle="Each ingestion run is one reversible unit. Deleting it removes the run's canonical and raw rows, matches, event memberships, coverage and partitions, then rebuilds the affected rollups."
      >
        {runs.isLoading ? (
          <p className="text-xs text-faint">Loading ingestion runs?</p>
        ) : (runs.data ?? []).length === 0 ? (
          <EmptyState
            title="No ingestion runs"
            description="Trigger an ingestion from Settings; runs appear here with their provenance."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line/10 text-2xs uppercase tracking-wide text-faint">
                  <th className="py-2 pr-4 font-normal">Source</th>
                  <th className="py-2 pr-4 font-normal">Window</th>
                  <th className="py-2 pr-4 font-normal">Inserted</th>
                  <th className="py-2 pr-4 font-normal">Status</th>
                  <th className="py-2 font-normal">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(runs.data ?? []).map((run) => {
                  const start = run.query_parameters?.start_date ?? "?";
                  const end = run.query_parameters?.end_date ?? start;
                  const label = `${run.source_code ?? "unknown"} ${start} ? ${end}`;
                  return (
                    <tr key={run.id} className="border-b border-line/[0.06] last:border-0">
                      <td className="py-2 pr-4 text-muted">{run.source_code ?? "?"}</td>
                      <td className="py-2 pr-4 text-muted">
                        {start} ? {end}
                      </td>
                      <td className="py-2 pr-4 text-muted">
                        {formatCount(run.records_inserted)}
                      </td>
                      <td className="py-2 pr-4 text-faint">{run.status}</td>
                      <td className="py-2">
                        <button
                          type="button"
                          onClick={() => void previewAndDeleteRun(run.id, label)}
                          disabled={run.status === "deleted" || deleteRun.isPending}
                          className="inline-flex items-center gap-1 rounded-full border border-danger/30 px-2 py-1 text-2xs text-danger transition-colors hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <Trash2 className="size-3" aria-hidden />
                          Delete data
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel
        className="mt-3"
        title="Exports"
        subtitle="Download an archive, then delete its range. Deletion is refused if the rows changed since the export."
      >
        {exports.isLoading ? (
          <p className="text-xs text-faint">Loading exports…</p>
        ) : (exports.data ?? []).length === 0 ? (
          <EmptyState
            title="No exports yet"
            description="Export a range above to create the first downloadable archive."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line/10 text-2xs uppercase tracking-wide text-faint">
                  <th className="py-2 pr-4 font-normal">Range</th>
                  <th className="py-2 pr-4 font-normal">Rows</th>
                  <th className="py-2 pr-4 font-normal">Size</th>
                  <th className="py-2 pr-4 font-normal">Created</th>
                  <th className="py-2 pr-4 font-normal">Status</th>
                  <th className="py-2 font-normal">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(exports.data ?? []).map((item) => (
                  <tr key={item.id} className="border-b border-line/[0.06] last:border-0">
                    <td className="py-2 pr-4 text-muted">
                      {item.start_date} → {item.end_date}
                    </td>
                    <td className="py-2 pr-4 text-muted">{formatCount(item.rows)}</td>
                    <td className="py-2 pr-4 text-muted">{formatBytes(item.size_bytes)}</td>
                    <td className="py-2 pr-4 text-faint">
                      {item.created_at ? item.created_at.slice(0, 16).replace("T", " ") : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      <span
                        className={
                          item.status === "deleted"
                            ? "text-2xs text-faint"
                            : "text-2xs text-accent"
                        }
                      >
                        {item.status}
                        {item.rows_deleted != null ? ` · ${formatCount(item.rows_deleted)} rows` : ""}
                      </span>
                    </td>
                    <td className="py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            void downloadExport(
                              item.id,
                              `${item.start_date}-${item.end_date}`,
                            )
                          }
                          disabled={downloading === item.id}
                          className="btn-glass inline-flex items-center gap-1 px-2 py-1 text-2xs disabled:opacity-40"
                        >
                          <Download className="size-3" aria-hidden />
                          {downloading === item.id ? "Downloading?" : "Download"}
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            runDelete(
                              item.id,
                              item.sha256,
                              `${item.start_date} → ${item.end_date}`,
                            )
                          }
                          disabled={item.status === "deleted" || deleteExport.isPending}
                          className="inline-flex items-center gap-1 rounded-full border border-danger/30 px-2 py-1 text-2xs text-danger transition-colors hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <Trash2 className="size-3" aria-hidden />
                          Delete raw
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel
        className="mt-3"
        title="Payload inventory by day"
        subtitle="What is actually on disk for provenance. Days past retention are removed by the retention job."
      >
        {inventory.isLoading ? (
          <p className="text-xs text-faint">Loading inventory…</p>
        ) : days.length === 0 ? (
          <EmptyState
            title="No raw payloads"
            description="The store holds canonical observations only; nothing is waiting for export."
          />
        ) : (
          <div className="max-h-[420px] overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-surface/90 backdrop-blur">
                <tr className="border-b border-line/10 text-2xs uppercase tracking-wide text-faint">
                  <th className="py-2 pr-4 font-normal">Day</th>
                  <th className="py-2 pr-4 font-normal">Rows</th>
                  <th className="py-2 pr-4 font-normal">Payload</th>
                  <th className="py-2 font-normal">State</th>
                </tr>
              </thead>
              <tbody>
                {days.map((day) => (
                  <tr key={day.day} className="border-b border-line/[0.06] last:border-0">
                    <td className="py-1.5 pr-4 text-muted">{day.day}</td>
                    <td className="py-1.5 pr-4 text-muted">{formatCount(day.rows)}</td>
                    <td className="py-1.5 pr-4 text-faint">
                      {day.payload_bytes != null ? formatBytes(day.payload_bytes) : "—"}
                    </td>
                    <td className="py-1.5">
                      {day.past_retention ? (
                        <span className="text-2xs text-warn">past retention</span>
                      ) : day.exportable ? (
                        <span className="text-2xs text-accent">exportable</span>
                      ) : (
                        <span className="text-2xs text-faint">too recent</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
