import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export interface FirmsKeyState {
  configured: boolean;
  source: "database" | "environment" | "runtime" | "none";
  masked: string | null;
  updated_at: string | null;
  hint: string;
}

export function useFirmsKey() {
  return useQuery({
    queryKey: ["admin", "firms-key"],
    queryFn: () => apiFetch<FirmsKeyState>("/api/v1/admin/settings/firms"),
  });
}

export function useSaveFirmsKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (apiKey: string) =>
      apiFetch<FirmsKeyState>("/api/v1/admin/settings/firms", {
        method: "PUT",
        body: JSON.stringify({ api_key: apiKey }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "firms-key"] });
      void queryClient.invalidateQueries({ queryKey: ["status"] });
    },
  });
}

export function useClearFirmsKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<FirmsKeyState>("/api/v1/admin/settings/firms", { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "firms-key"] });
      void queryClient.invalidateQueries({ queryKey: ["status"] });
    },
  });
}

export function useTestFirmsKey() {
  return useMutation({
    mutationFn: () =>
      apiFetch<{
        ok: boolean;
        source_code: string;
        min_date: string | null;
        max_date: string | null;
      }>("/api/v1/admin/settings/firms/test", { method: "POST" }),
  });
}


export interface IngestionRun {
  id: string;
  source_code: string | null;
  status: string;
  started_at: string;
  records_received: number;
  records_inserted: number;
  query_parameters: { start_date?: string; end_date?: string; tile?: string };
}

export interface RunDeletePreview {
  run_id: string;
  source_code: string | null;
  start_date: string;
  end_date: string;
  observations: number;
  raw_observations: number;
  matches: number;
  partitions: number;
  already_deleted: boolean;
}

export function useIngestionRuns(limit = 20) {
  return useQuery({
    queryKey: ["admin", "ingestion-runs", limit],
    queryFn: () =>
      apiFetch<IngestionRun[]>(`/api/v1/admin/ingestion/jobs?limit=${limit}`),
    staleTime: 15_000,
  });
}

export async function previewRunDelete(runId: string): Promise<RunDeletePreview> {
  return apiFetch<RunDeletePreview>(
    `/api/v1/admin/ingestion/runs/${runId}/preview`,
  );
}

export function useDeleteRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) =>
      apiFetch<RunDeletePreview & { deleted: boolean }>(
        `/api/v1/admin/ingestion/runs/${runId}/delete`,
        { method: "POST", body: JSON.stringify({ confirm: true }) },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["calendar"] });
      void queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}


export interface TileOption {
  key: string;
  bbox: string;
}

export interface AdminSource {
  code: string;
  sensor: string;
  satellite: string;
  registered: boolean;
  observations: number;
}

export function useAdminSources() {
  return useQuery({
    queryKey: ["admin", "sources"],
    queryFn: () => apiFetch<AdminSource[]>("/api/v1/admin/ingestion/sources"),
    staleTime: 60_000,
  });
}

export function useIngestionTiles() {
  return useQuery({
    queryKey: ["admin", "tiles"],
    queryFn: () => apiFetch<TileOption[]>("/api/v1/admin/ingestion/tiles"),
    staleTime: 600_000,
  });
}

export function useRunIngestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      source_code: string;
      start_date: string;
      end_date: string;
      tile?: string;
      run_harmonization?: boolean;
    }) =>
      apiFetch<Record<string, unknown>>("/api/v1/admin/ingestion/run", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });
}

export function useRunAllSources() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      start_date: string;
      end_date: string;
      tile?: string;
    }) =>
      apiFetch<Record<string, unknown>>("/api/v1/admin/ingestion/run-all", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });
}

export function useCheckAvailability() {
  return useMutation({
    mutationFn: (input: {
      source_code: string;
      start_date: string;
      end_date: string;
    }) =>
      apiFetch<Record<string, unknown>>("/api/v1/admin/ingestion/availability", {
        method: "POST",
        body: JSON.stringify(input),
      }),
  });
}

export interface HistoryDataset {
  key: string;
  label: string;
  source_code: string;
  sensor: string;
}

export interface HistoryJob {
  id: string;
  status: string;
  start_date: string;
  end_date: string;
  region: string | null;
  created_at: string;
  progress?: Record<string, unknown>;
}

export function useHistoryDatasets() {
  return useQuery({
    queryKey: ["history", "datasets"],
    queryFn: () => apiFetch<HistoryDataset[]>("/api/v1/history/datasets"),
    staleTime: 600_000,
  });
}

export function useHistoryJobs() {
  return useQuery({
    queryKey: ["history", "jobs"],
    queryFn: () => apiFetch<HistoryJob[]>("/api/v1/history/jobs?limit=10"),
    refetchInterval: 10_000,
  });
}

export function useCreateHistoryJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      datasets: string[];
      start_date: string;
      end_date: string;
      region?: string;
      harmonize: boolean;
    }) =>
      apiFetch<HistoryJob>("/api/v1/history/jobs", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["history"] }),
  });
}

export function useHistoryAction(action: "cancel" | "resume") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      apiFetch<HistoryJob>(`/api/v1/history/jobs/${jobId}/${action}`, {
        method: "POST",
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["history"] }),
  });
}

export function useRebuildRollups() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { start_date: string; end_date: string }) =>
      apiFetch<Record<string, unknown>>("/api/v1/admin/maintenance/rollups", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => void queryClient.invalidateQueries(),
  });
}

export function useClearCaches() {
  return useMutation({
    mutationFn: () =>
      apiFetch<Record<string, unknown>>("/api/v1/admin/maintenance/cache/clear", {
        method: "POST",
      }),
  });
}
