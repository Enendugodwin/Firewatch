import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { fetchHarmonizedSeries } from "@/lib/intelligenceApi";
import type {
  AlgorithmRunOut,
  IngestAllResponse,
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

export function useHarmonizationSummary(start?: string, end?: string) {
  const params = new URLSearchParams();
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  const query = params.toString();
  return useQuery({
    queryKey: [...queryKeys.harmonization, start ?? "", end ?? ""],
    queryFn: () =>
      apiFetch<HarmonizationSummary>(
        `/api/v1/harmonization/summary${query ? `?${query}` : ""}`,
      ),
    staleTime: 30_000,
  });
}

export function useHarmonizedSeries(start: string, end: string) {
  return useQuery({
    queryKey: ["harmonized-series", start, end],
    queryFn: ({ signal }) => fetchHarmonizedSeries(start, end, signal),
    staleTime: 60_000,
    retry: 1,
  });
}

export function useMatches(status?: string, start?: string, end?: string) {
  const params = new URLSearchParams({ limit: "50" });
  if (status) params.set("status", status);
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  return useQuery({
    queryKey: [...queryKeys.matches(status), start ?? "", end ?? ""],
    queryFn: () => apiFetch<MatchPage>(`/api/v1/harmonization/matches?${params.toString()}`),
    staleTime: 30_000,
  });
}

export function useEvents(start?: string, end?: string) {
  const params = new URLSearchParams({ limit: "25" });
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  return useQuery({
    queryKey: [...queryKeys.events, start ?? "", end ?? ""],
    queryFn: () => apiFetch<FireEventOut[]>(`/api/v1/harmonization/events?${params}`),
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
      void queryClient.invalidateQueries({ queryKey: ["analytics"] });
      void queryClient.invalidateQueries({ queryKey: ["anomalies"] });
      void queryClient.invalidateQueries({ queryKey: ["calendar"] });
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

export interface IngestAllProgress {
  done: number;
  total: number;
  current: string;
  result: IngestResponse | null;
}

export interface IngestAllPayload {
  start_date: string;
  end_date: string;
  source_codes: string[];
  run_harmonization?: boolean;
  run_events?: boolean;
  onProgress?: (progress: IngestAllProgress) => void;
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
      // Ingestion changes almost every derived view (map, calendar, analytics,
      // anomalies, query, sources), so refresh the whole cache rather than a
      // hand-picked subset that silently goes stale.
      void queryClient.invalidateQueries();
    },
  });
}

/**
 * Ingest the same window for every registered source. The loop runs one request
 * per source so the console can show real progress and a per-source outcome; the
 * aggregate /run-all endpoint remains available for scripts and API clients.
 */
export function useRunAllIngestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      onProgress,
      run_harmonization = true,
      run_events = true,
      ...payload
    }: IngestAllPayload) => {
      const codes = payload.source_codes;
      const results: IngestResponse[] = [];
      let inserted = 0;
      let received = 0;
      let rejected = 0;

      for (const [index, code] of codes.entries()) {
        onProgress?.({ done: index, total: codes.length, current: code, result: null });
        let result: IngestResponse;
        try {
          result = await apiFetch<IngestResponse>("/api/v1/admin/ingestion/run", {
            method: "POST",
            body: JSON.stringify({
              source_code: code,
              start_date: payload.start_date,
              end_date: payload.end_date,
              run_harmonization: false,
            }),
          });
        } catch (error) {
          result = {
            run_id: null,
            source_code: code,
            status: "failed",
            records_received: 0,
            records_inserted: 0,
            records_rejected: 0,
            partitions_completed: 0,
            partitions_skipped: 0,
            rejections: {},
            errors: [error instanceof Error ? error.message : String(error)],
            is_synthetic: false,
            harmonization: null,
            events: null,
          };
        }
        results.push(result);
        inserted += result.records_inserted;
        received += result.records_received;
        rejected += result.records_rejected;
        onProgress?.({ done: index + 1, total: codes.length, current: code, result });
      }

      let harmonization: Record<string, unknown> | null = null;
      let events: Record<string, unknown> | null = null;
      if (inserted > 0 && run_harmonization) {
        try {
          const outcome = await apiFetch<{
            scopes?: Record<string, unknown>[];
            events?: Record<string, unknown>[];
          }>("/api/v1/harmonization/run", {
            method: "POST",
            body: JSON.stringify({ run_events }),
          });
          harmonization = { scopes: outcome.scopes ?? [] };
          events = outcome.events?.length ? { events: outcome.events.length } : null;
        } catch {
          harmonization = null;
        }
      }

      const succeeded = results.filter((item) => item.status !== "failed").length;
      return {
        start_date: payload.start_date,
        end_date: payload.end_date,
        sources_requested: codes.length,
        sources_succeeded: succeeded,
        sources_failed: codes.length - succeeded,
        records_received: received,
        records_inserted: inserted,
        records_rejected: rejected,
        results,
        harmonization,
        events,
      } satisfies IngestAllResponse;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries();
    },
  });
}
