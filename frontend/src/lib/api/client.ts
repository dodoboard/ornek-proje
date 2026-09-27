import type { components } from "./schema";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type SystemResponse = components["schemas"]["SystemResponse"];

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");

/** Normalised error for every failed API call. `code` mirrors the backend ErrorCode. */
export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ErrorEnvelope {
  error: { code: string; message: string };
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const error = (value as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}

export async function apiFetch<T>(path: string, init?: RequestInit, fetchImpl: typeof fetch = fetch): Promise<T> {
  let response: Response;
  try {
    response = await fetchImpl(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("BACKEND_UNREACHABLE", "Cannot reach the local backend. Is it running?", 0);
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (isErrorEnvelope(body)) throw new ApiError(body.error.code, body.error.message, response.status);
    throw new ApiError(`HTTP_${response.status}`, "The backend returned an unexpected error.", response.status);
  }
  return body as T;
}

export const api = {
  health: () => apiFetch<HealthResponse>("/api/health"),
  system: () => apiFetch<SystemResponse>("/api/system"),
};
