import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export interface StorageReport {
  mode: string;
  local_directory: string;
  database_mode: string;
  r2_bucket: string | null;
  r2_configured: boolean;
  available: boolean;
  provider?: string;
  used_bytes?: number;
  free_bytes?: number;
  allocation_bytes?: number;
  error?: string;
}

export interface InfrastructureStatus {
  deployment_mode: string;
  database_mode: string;
  storage: StorageReport;
  database: {
    dialect: string;
    size_bytes: number;
    tables: number;
    cloud_database_configured: boolean;
  };
  rollups: { available: boolean; rows?: number; dialect: string };
}

export interface DatasetEntry {
  dataset: string;
  path: string;
  kind: string;
  sensor: string;
  coverage_start: string;
  coverage_end: string;
  partition: string;
  records: number;
  size_bytes: number;
  checksum: string;
  schema_version: string;
  processing_version: string;
  local_path: string;
  sync_status?: string;
}

export interface DatasetInventory {
  root: string;
  count: number;
  total_bytes: number;
  records: number;
  datasets: DatasetEntry[];
}

export interface SyncPreview {
  previewed_at: string;
  counts: Record<string, number>;
  upload_bytes: number;
  remote_used_bytes: number;
  files: DatasetEntry[];
}

export interface SyncReport {
  status: string;
  uploaded?: number;
  skipped?: number;
  failed?: number;
  verified?: number;
  upload_bytes?: number;
  remote_used_bytes?: number;
  allocation_bytes?: number;
  reason?: string;
  detail?: string;
  results: DatasetEntry[];
}

export function fetchInfrastructure(signal?: AbortSignal) {
  return apiFetch<InfrastructureStatus>("/api/v1/infrastructure/status", { signal });
}

export function testStorage() {
  return apiFetch<Record<string, unknown>>("/api/v1/infrastructure/storage/test", { method: "POST" });
}

export function exportDatasets(startDate: string, endDate: string) {
  return apiFetch<{ written: number; manifest: Record<string, number> }>(
    "/api/v1/infrastructure/export",
    {
      method: "POST",
      body: JSON.stringify({ start_date: startDate, end_date: endDate, include_analytics: true }),
    },
  );
}

export function fetchDatasets(signal?: AbortSignal) {
  return apiFetch<DatasetInventory>("/api/v1/infrastructure/datasets", { signal });
}

export function previewSync() {
  return apiFetch<SyncPreview>("/api/v1/infrastructure/sync/preview", { method: "POST" });
}

export function runSync() {
  return apiFetch<SyncReport>("/api/v1/infrastructure/sync", {
    method: "POST",
    body: JSON.stringify({ verify: true }),
  });
}

export function useInfrastructure() {
  return useQuery({
    queryKey: ["infrastructure"],
    queryFn: ({ signal }) => fetchInfrastructure(signal),
    staleTime: 30_000,
    retry: 1,
  });
}

export function useDatasets() {
  return useQuery({
    queryKey: ["infrastructure", "datasets"],
    queryFn: ({ signal }) => fetchDatasets(signal),
    staleTime: 30_000,
  });
}

export function useSyncActions() {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["infrastructure"] });

  const exportRun = useMutation({
    mutationFn: ({ startDate, endDate }: { startDate: string; endDate: string }) =>
      exportDatasets(startDate, endDate),
    onSuccess: invalidate,
  });
  const preview = useMutation({ mutationFn: previewSync });
  const sync = useMutation({ mutationFn: runSync, onSuccess: invalidate });
  const test = useMutation({ mutationFn: testStorage, onSuccess: invalidate });

  return { exportRun, preview, sync, test };
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(size >= 100 ? 0 : 1)} ${units[index]}`;
}
