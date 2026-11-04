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
