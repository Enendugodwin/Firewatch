import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type {
  AlgorithmRunOut,
  DashboardOverview,
  FireEventOut,
  HarmonizationSummary,
  IngestResponse,
  IngestionRunOut,
  MatchPage,
  ModuleStatusItem,
  SourceHealth,
  SourceOut,
  SystemStatus,
} from "@/types/api";

export const queryKeys = {
  systemStatus: ["system", "status"] as const,
  modules: ["system", "modules"] as const,
  sources: ["system", "sources"] as const,
  dashboard: ["dashboard"] as const,
  harmonization: ["harmonization", "summary"] as const,
  matches: (status?: string) => ["harmonization", "matches", status ?? "all"] as const,
  events: ["harmonization", "events"] as const,
  algorithmRuns: ["harmonization", "jobs"] as const,
  ingestionRuns: ["ingestion", "jobs"] as const,
  sourceHealth: ["ingestion", "sources"] as const,
};

export function useSystemStatus() {
  return useQuery({
    queryKey: queryKeys.systemStatus,
    queryFn: () => apiFetch<SystemStatus>("/api/v1/system/status"),
    staleTime: 15_000,
    refetchInterval: 60_000,
    retry: 1,
  });
}

export function useModules() {
  return useQuery({
    queryKey: queryKeys.modules,
    queryFn: () => apiFetch<ModuleStatusItem[]>("/api/v1/system/modules"),
    staleTime: 5 * 60_000,
  });
}

export function useSources() {
  return useQuery({
    queryKey: queryKeys.sources,
    queryFn: () => apiFetch<SourceOut[]>("/api/v1/system/sources"),
    staleTime: 15_000,
  });
}

export function useDashboardOverview() {
  return useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: () => apiFetch<DashboardOverview>("/api/v1/dashboard"),
    staleTime: 30_000,
  });
}

export function useHarmonizationSummary() {
  return useQuery({
    queryKey: queryKeys.harmonization,
    queryFn: () => apiFetch<HarmonizationSummary>("/api/v1/harmonization/summary"),
    staleTime: 30_000,
  });
}

export function useMatches(status?: string) {
  return useQuery({
    queryKey: queryKeys.matches(status),
    queryFn: () =>
      apiFetch<MatchPage>(
        `/api/v1/harmonization/matches?limit=50${status ? `&status=${status}` : ""}`,
      ),
    staleTime: 30_000,
  });
}

export function useEvents() {
  return useQuery({
    queryKey: queryKeys.events,
    queryFn: () => apiFetch<FireEventOut[]>("/api/v1/harmonization/events?limit=25"),
    staleTime: 30_000,
  });
}

export function useAlgorithmRuns() {
  return useQuery({
    queryKey: queryKeys.algorithmRuns,
    queryFn: () => apiFetch<AlgorithmRunOut[]>("/api/v1/harmonization/jobs?limit=10"),
    staleTime: 30_000,
  });
}

export function useIngestionRuns() {
  return useQuery({
    queryKey: queryKeys.ingestionRuns,
    queryFn: () => apiFetch<IngestionRunOut[]>("/api/v1/admin/ingestion/jobs?limit=10"),
    staleTime: 15_000,
  });
}

export function useSourceHealth() {
  return useQuery({
    queryKey: queryKeys.sourceHealth,
    queryFn: () => apiFetch<SourceHealth[]>("/api/v1/admin/ingestion/sources"),
    staleTime: 30_000,
  });
}

export interface HarmonizationScope {
  start_date?: string;
  end_date?: string;
  bbox?: string;
}

/** Re-run cross-sensor association and event grouping for a bounded scope. */
export function useRunHarmonization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scope: HarmonizationScope = {}) =>
      apiFetch<{ scopes: Record<string, unknown>[]; events: Record<string, unknown>[] }>(
        "/api/v1/harmonization/run",
        { method: "POST", body: JSON.stringify(scope) },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["harmonization"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.systemStatus });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

export interface IngestPayload {
  source_code: string;
  start_date: string;
  end_date: string;
  tile?: string;
  run_harmonization?: boolean;
  run_events?: boolean;
}

export function useRunIngestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: IngestPayload) =>
      apiFetch<IngestResponse>("/api/v1/admin/ingestion/run", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.ingestionRuns });
      void queryClient.invalidateQueries({ queryKey: queryKeys.sourceHealth });
      void queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      void queryClient.invalidateQueries({ queryKey: queryKeys.systemStatus });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
      void queryClient.invalidateQueries({ queryKey: ["harmonization"] });
    },
  });
}
