import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export interface RawDay {
  day: string;
  rows: number;
  payload_bytes: number | null;
  exportable: boolean;
  past_retention: boolean;
}

export interface RawInventory {
  policy: {
    retention_days: number;
    retention_cutoff: string;
    export_min_age_days: number;
    export_cutoff: string;
    export_max_days: number;
  };
  totals: {
    rows: number;
    payload_bytes: number | null;
    days: number;
    past_retention_rows: number;
  };
  days: RawDay[];
}

export interface RawExport {
  id: string;
  start_date: string;
  end_date: string;
  rows: number;
  size_bytes: number;
  sha256: string;
  status: "ready" | "deleted";
  created_at: string | null;
  deleted_at: string | null;
  rows_deleted: number | null;
}

export function useRawInventory() {
  return useQuery({
    queryKey: ["raw-archive", "inventory"],
    queryFn: () => apiFetch<RawInventory>("/api/v1/admin/raw/inventory"),
  });
}

export function useRawExports() {
  return useQuery({
    queryKey: ["raw-archive", "exports"],
    queryFn: () => apiFetch<RawExport[]>("/api/v1/admin/raw/exports"),
  });
}

export function useCreateRawExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { start_date: string; end_date: string }) =>
      apiFetch<RawExport>("/api/v1/admin/raw/exports", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["raw-archive"] });
    },
  });
}

export function useDeleteRawExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; confirm_sha256: string }) =>
      apiFetch<{ export_id: string; rows_deleted: number }>(
        `/api/v1/admin/raw/exports/${input.id}/delete`,
        {
          method: "POST",
          body: JSON.stringify({ confirm_sha256: input.confirm_sha256 }),
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["raw-archive"] });
    },
  });
}

export function useRunRetention() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { days?: number }) =>
      apiFetch<{
        days: number;
        cutoff: string;
        rows: number;
        applied: boolean;
        rows_deleted?: number;
      }>("/api/v1/admin/raw/retention", {
        method: "POST",
        body: JSON.stringify({ ...input, confirm: true }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["raw-archive"] });
    },
  });
}
