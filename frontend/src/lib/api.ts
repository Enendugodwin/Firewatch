import type { ApiErrorBody } from "@/types/api";

/**
 * The browser never holds secrets and never talks to NASA directly: every
 * request goes to our own API, which owns the FIRMS MAP_KEY.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;

  constructor(
    message: string,
    options: {
      code: string;
      status: number;
      details?: Record<string, unknown>;
      requestId?: string | null;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.code = options.code;
    this.status = options.status;
    this.details = options.details ?? {};
    this.requestId = options.requestId ?? null;
  }

  /** True when the endpoint exists but its module is not built yet (501). */
  get isPending() {
    return this.code === "not_implemented";
  }

  get plannedForPhase() {
    const value = this.details["planned_for_phase"];
    return typeof value === "string" ? value : null;
  }
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as ApiErrorBody).error?.code === "string"
  );
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch (cause) {
    throw new ApiError(
      "The FIREWATCH X API is unreachable. Start the backend on port 8100.",
      { code: "network_error", status: 0, details: { cause: String(cause) } },
    );
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    if (isErrorBody(payload)) {
      const { error } = payload;
      throw new ApiError(error.message, {
        code: error.code,
        status: response.status,
        details: error.details,
        requestId: error.request_id,
      });
    }
    throw new ApiError(`Request failed with status ${response.status}.`, {
      code: "unknown_error",
      status: response.status,
    });
  }

  return payload as T;
}
