import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataRow, Panel } from "@/components/ui/Panel";
import {
  useAdminSources,
  useCheckAvailability,
  useClearCaches,
  useCreateHistoryJob,
  useHistoryAction,
  useHistoryDatasets,
  useHistoryJobs,
  useIngestionTiles,
  useRebuildRollups,
  useRunAllSources,
  useRunIngestion,
} from "@/lib/adminApi";
import { useAuthStatus, useCreateUser, usePatchUser, useUsers } from "@/lib/authApi";
import { useRunHarmonization } from "@/lib/queries";

function isoDaysAgo(days: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - days);
  return date.toISOString().slice(0, 10);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const inputClass =
  "rounded-lg border border-line/10 bg-line/[0.03] px-3 py-2 text-xs text-ink";

export function ServiceControls() {
  const auth = useAuthStatus();
  const isAdmin = Boolean(auth.data?.open_access || auth.data?.user?.role === "admin");

  const sources = useAdminSources();
  const tiles = useIngestionTiles();
  const runIngestion = useRunIngestion();
  const runAll = useRunAllSources();
  const availability = useCheckAvailability();

  const [source, setSource] = useState("MODIS_NRT");
  const [tile, setTile] = useState("world");
  const [start, setStart] = useState(isoDaysAgo(1));
  const [end, setEnd] = useState(todayIso());
  const [ingestNotice, setIngestNotice] = useState<string | null>(null);

  const datasets = useHistoryDatasets();
  const jobs = useHistoryJobs();
  const createJob = useCreateHistoryJob();
  const cancelJob = useHistoryAction("cancel");
  const resumeJob = useHistoryAction("resume");
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>([]);
  const [historyRegion, setHistoryRegion] = useState("");
  const [harmonize, setHarmonize] = useState(false);
  const [historyNotice, setHistoryNotice] = useState<string | null>(null);

  const runHarmonization = useRunHarmonization();
  const rebuild = useRebuildRollups();
  const clearCaches = useClearCaches();
  const [maintenanceNotice, setMaintenanceNotice] = useState<string | null>(null);

  const users = useUsers(isAdmin);
  const createUser = useCreateUser();
  const patchUser = usePatchUser();
  const [newUser, setNewUser] = useState({
    email: "",
    display_name: "",
    password: "",
    role: "viewer",
  });
  const [userNotice, setUserNotice] = useState<string | null>(null);

  const sourceCodes = (sources.data ?? []).map((item) => item.code);

  const doIngest = () => {
    setIngestNotice(null);
    runIngestion.mutate(
      { source_code: source, start_date: start, end_date: end, tile, run_harmonization: false },
      {
        onSuccess: (result) =>
          setIngestNotice(
            `Ingestion finished: ${String(result.status ?? "ok")} · inserted ${String(
              result.records_inserted ?? 0,
            )} · received ${String(result.records_received ?? 0)}.`,
          ),
        onError: (error) => setIngestNotice(error.message),
      },
    );
  };

  const doRunAll = () => {
    setIngestNotice(null);
    runAll.mutate(
      { start_date: start, end_date: end, tile },
      {
        onSuccess: (result) =>
          setIngestNotice(
            `All-source run finished; ${String(result.sources_succeeded ?? "?")}/${String(
              result.sources_requested ?? "?",
            )} sources succeeded.`,
          ),
        onError: (error) => setIngestNotice(error.message),
      },
    );
  };

  const doAvailability = () => {
    setIngestNotice(null);
    availability.mutate(
      { source_code: source, start_date: start, end_date: end },
      {
        onSuccess: (result) =>
          setIngestNotice(`Availability: ${JSON.stringify(result).slice(0, 240)}`),
        onError: (error) => setIngestNotice(error.message),
      },
    );
  };

  const startHistory = () => {
    setHistoryNotice(null);
    if (selectedDatasets.length === 0) {
      setHistoryNotice("Select at least one dataset.");
      return;
    }
    createJob.mutate(
      {
        datasets: selectedDatasets,
        start_date: start,
        end_date: end,
        region: historyRegion || undefined,
        harmonize,
      },
      {
        onSuccess: (job) => setHistoryNotice(`Job ${job.id.slice(0, 8)} queued.`),
        onError: (error) => setHistoryNotice(error.message),
      },
    );
  };

  const doHarmonize = () => {
    setMaintenanceNotice(null);
    runHarmonization.mutate(
      { start_date: start, end_date: end },
      {
        onSuccess: (result) =>
          setMaintenanceNotice(
            `Harmonization complete for ${(result.scopes ?? []).length} scope(s).`,
          ),
        onError: (error) => setMaintenanceNotice(error.message),
      },
    );
  };

  const submitUser = () => {
    setUserNotice(null);
    createUser.mutate(newUser, {
      onSuccess: (user) => {
        setUserNotice(`Created ${user.email} (${user.role}).`);
        setNewUser({ email: "", display_name: "", password: "", role: "viewer" });
      },
      onError: (error) => setUserNotice(error.message),
    });
  };

  return (
    <>
      {isAdmin ? (
        <Panel
          className="mt-3"
          title="Operator accounts"
          subtitle="Argon2id passwords, roles and revocable sessions. Admin can manage everything; analyst can ingest and analyse; viewer is read-only."
        >
          <div className="flex flex-wrap items-end gap-2">
            <input
              className={inputClass}
              placeholder="email@example.com"
              value={newUser.email}
              onChange={(event) => setNewUser({ ...newUser, email: event.target.value })}
            />
            <input
              className={inputClass}
              placeholder="Display name"
              value={newUser.display_name}
              onChange={(event) =>
                setNewUser({ ...newUser, display_name: event.target.value })
              }
            />
            <input
              className={inputClass}
              type="password"
              placeholder="Password (10+ chars)"
              value={newUser.password}
              onChange={(event) => setNewUser({ ...newUser, password: event.target.value })}
            />
            <select
              className={inputClass}
              value={newUser.role}
              onChange={(event) => setNewUser({ ...newUser, role: event.target.value })}
            >
              <option value="viewer">viewer</option>
              <option value="analyst">analyst</option>
              <option value="admin">admin</option>
            </select>
            <Button variant="primary" onClick={submitUser} disabled={createUser.isPending}>
              {createUser.isPending ? "Creating…" : "Create account"}
            </Button>
          </div>
          {userNotice ? <p className="mt-2 text-2xs text-muted">{userNotice}</p> : null}
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line/10 text-2xs uppercase tracking-wide text-faint">
                  <th className="py-2 pr-4 font-normal">Email</th>
                  <th className="py-2 pr-4 font-normal">Role</th>
                  <th className="py-2 pr-4 font-normal">Active</th>
                  <th className="py-2 font-normal">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(users.data ?? []).map((user) => (
                  <tr key={user.id} className="border-b border-line/[0.06] last:border-0">
                    <td className="py-2 pr-4 text-muted">
                      {user.email}
                      <span className="ml-2 text-2xs text-faint">{user.display_name}</span>
                    </td>
                    <td className="py-2 pr-4">
                      <select
                        className={inputClass}
                        value={user.role}
                        onChange={(event) =>
                          patchUser.mutate({ id: user.id, role: event.target.value })
                        }
                      >
                        <option value="viewer">viewer</option>
                        <option value="analyst">analyst</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td className="py-2 pr-4">
                      <Badge tone={user.is_active ? "ok" : "neutral"}>
                        {user.is_active ? "active" : "disabled"}
                      </Badge>
                    </td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="btn-glass px-2 py-1 text-2xs"
                          onClick={() => {
                            const password = window.prompt(
                              `New password for ${user.email} (10+ characters):`,
                            );
                            if (password) {
                              patchUser.mutate({ id: user.id, password });
                            }
                          }}
                        >
                          Reset password
                        </button>
                        <button
                          type="button"
                          className="btn-glass px-2 py-1 text-2xs"
                          onClick={() =>
                            patchUser.mutate({ id: user.id, is_active: !user.is_active })
                          }
                        >
                          {user.is_active ? "Disable" : "Enable"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      ) : null}

      <Panel
        className="mt-3"
        title="Ingestion control"
        subtitle="Five-day windows, per source or every registered product. Ingestion never invents a day: unavailable coverage is reported."
      >
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-2xs text-faint">
            Source
            <select
              className={inputClass}
              value={source}
              onChange={(event) => setSource(event.target.value)}
            >
              {(sourceCodes.length ? sourceCodes : [source]).map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-2xs text-faint">
            Tile
            <select
              className={inputClass}
              value={tile}
              onChange={(event) => setTile(event.target.value)}
            >
              {(tiles.data ?? [{ key: "world", bbox: "world" }]).map((item) => (
                <option key={item.key} value={item.key}>
                  {item.key}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-2xs text-faint">
            Start
            <input
              type="date"
              className={inputClass}
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-2xs text-faint">
            End
            <input
              type="date"
              className={inputClass}
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </label>
          <Button variant="primary" onClick={doIngest} disabled={runIngestion.isPending}>
            {runIngestion.isPending ? "Ingesting…" : "Run window"}
          </Button>
          <Button variant="secondary" onClick={doRunAll} disabled={runAll.isPending}>
            {runAll.isPending ? "Running all…" : "Run all sources"}
          </Button>
          <Button variant="secondary" onClick={doAvailability} disabled={availability.isPending}>
            Check availability
          </Button>
        </div>
        {ingestNotice ? <p className="mt-2 text-2xs text-muted">{ingestNotice}</p> : null}
      </Panel>

      <Panel
        className="mt-3"
        title="Historical backfill"
        subtitle="Durable jobs for multi-year ranges. Progress is checkpointed per window and survives a restart."
      >
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[260px]">
            <div className="text-2xs text-faint">Datasets</div>
            <div className="mt-1 flex flex-wrap gap-2">
              {(datasets.data ?? []).map((dataset) => (
                <label
                  key={dataset.key}
                  className="inline-flex items-center gap-1 text-2xs text-muted"
                >
                  <input
                    type="checkbox"
                    checked={selectedDatasets.includes(dataset.key)}
                    onChange={(event) =>
                      setSelectedDatasets((current) =>
                        event.target.checked
                          ? [...current, dataset.key]
                          : current.filter((key) => key !== dataset.key),
                      )
                    }
                  />
                  {dataset.key}
                </label>
              ))}
            </div>
          </div>
          <input
            className={inputClass}
            placeholder="Region (optional)"
            value={historyRegion}
            onChange={(event) => setHistoryRegion(event.target.value)}
          />
          <label className="inline-flex items-center gap-2 text-2xs text-muted">
            <input
              type="checkbox"
              checked={harmonize}
              onChange={(event) => setHarmonize(event.target.checked)}
            />
            Harmonize after ingest
          </label>
          <Button variant="primary" onClick={startHistory} disabled={createJob.isPending}>
            {createJob.isPending ? "Queuing…" : "Start backfill"}
          </Button>
        </div>
        {historyNotice ? <p className="mt-2 text-2xs text-muted">{historyNotice}</p> : null}
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line/10 text-2xs uppercase tracking-wide text-faint">
                <th className="py-2 pr-4 font-normal">Job</th>
                <th className="py-2 pr-4 font-normal">Window</th>
                <th className="py-2 pr-4 font-normal">Status</th>
                <th className="py-2 font-normal">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(jobs.data ?? []).map((job) => (
                <tr key={job.id} className="border-b border-line/[0.06] last:border-0">
                  <td className="py-2 pr-4 font-mono text-2xs text-faint">{job.id.slice(0, 8)}</td>
                  <td className="py-2 pr-4 text-muted">
                    {job.start_date} → {job.end_date}
                  </td>
                  <td className="py-2 pr-4">
                    <Badge
                      tone={
                        job.status === "succeeded"
                          ? "ok"
                          : job.status === "failed"
                            ? "warn"
                            : "info"
                      }
                    >
                      {job.status}
                    </Badge>
                  </td>
                  <td className="py-2">
                    {job.status === "running" || job.status === "queued" ? (
                      <button
                        type="button"
                        className="btn-glass px-2 py-1 text-2xs"
                        onClick={() => cancelJob.mutate(job.id)}
                      >
                        Cancel
                      </button>
                    ) : job.status === "failed" || job.status === "cancelled" ? (
                      <button
                        type="button"
                        className="btn-glass px-2 py-1 text-2xs"
                        onClick={() => resumeJob.mutate(job.id)}
                      >
                        Resume
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel
        className="mt-3"
        title="Analysis maintenance"
        subtitle="Harmonization, rollup rebuilds and cache resets for the selected period."
      >
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={doHarmonize} disabled={runHarmonization.isPending}>
            {runHarmonization.isPending ? "Harmonizing…" : "Run harmonization"}
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              rebuild.mutate(
                { start_date: start, end_date: end },
                {
                  onSuccess: () => setMaintenanceNotice("Rollups rebuilt."),
                  onError: (error) => setMaintenanceNotice(error.message),
                },
              )
            }
            disabled={rebuild.isPending}
          >
            {rebuild.isPending ? "Rebuilding…" : "Rebuild rollups"}
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              clearCaches.mutate(undefined, {
                onSuccess: () => setMaintenanceNotice("Caches cleared."),
                onError: (error) => setMaintenanceNotice(error.message),
              })
            }
            disabled={clearCaches.isPending}
          >
            Clear caches
          </Button>
        </div>
        {maintenanceNotice ? (
          <p className="mt-2 text-2xs text-muted">{maintenanceNotice}</p>
        ) : null}
        <div className="mt-3">
          <DataRow label="Selected maintenance period">
            {start} → {end}
          </DataRow>
        </div>
      </Panel>
    </>
  );
}
