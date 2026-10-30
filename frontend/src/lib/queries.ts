import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { ModuleStatusItem, SourceOut, SystemStatus } from "@/types/api";

export const queryKeys = {
  systemStatus: ["system", "status"] as const,
  modules: ["system", "modules"] as const,
  sources: ["system", "sources"] as const,
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
    staleTime: 5 * 60_000,
  });
}
