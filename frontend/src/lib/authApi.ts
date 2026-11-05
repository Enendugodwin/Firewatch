import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "analyst" | "viewer";
  is_active: boolean;
  created_at?: string | null;
}

export interface AuthStatus {
  authentication: boolean;
  authenticated: boolean;
  required: boolean;
  open_access: boolean;
  user: AuthUser | null;
  roles: string[];
  method: string;
}

export function useAuthStatus() {
  return useQuery({
    queryKey: ["auth", "status"],
    queryFn: () => apiFetch<AuthStatus>("/api/v1/auth/status"),
    staleTime: 30_000,
    retry: 1,
  });
}

export function useUsers(enabled = true) {
  return useQuery({
    queryKey: ["auth", "users"],
    queryFn: () => apiFetch<AuthUser[]>("/api/v1/auth/users"),
    enabled,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      email: string;
      password: string;
      display_name: string;
      role: string;
    }) =>
      apiFetch<AuthUser>("/api/v1/auth/users", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["auth"] }),
  });
}

export function usePatchUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      id: string;
      role?: string;
      is_active?: boolean;
      display_name?: string;
      password?: string;
    }) =>
      apiFetch<AuthUser>(`/api/v1/auth/users/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          role: input.role,
          is_active: input.is_active,
          display_name: input.display_name,
          password: input.password,
        }),
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["auth"] }),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch("/api/v1/auth/logout", { method: "POST" }),
    onSuccess: () => void queryClient.invalidateQueries(),
  });
}
