import type { components } from "./schema";

type Schemas = components["schemas"];

export type HealthResponse = Schemas["HealthResponse"];
export type SystemResponse = Schemas["SystemResponse"];
export type ProjectRead = Schemas["ProjectRead"];
export type ProjectCreate = Schemas["ProjectCreate"];
export type ProjectType = ProjectRead["type"];
export type ProjectSettings = Schemas["ProjectSettings"];
export type CharacterSummary = Schemas["CharacterSummary"];
export type ProductSummary = Schemas["ProductSummary"];
export type PropertySummary = Schemas["PropertySummary"];
export type JobRead = Schemas["JobRead"];
export type JobStatus = JobRead["status"];
export type WorkerStatus = Schemas["WorkerStatus"];

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

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

  if (response.status === 204) return undefined as T;

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (isErrorEnvelope(body)) throw new ApiError(body.error.code, body.error.message, response.status);
    throw new ApiError(`HTTP_${response.status}`, "The backend returned an unexpected error.", response.status);
  }
  return body as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return { method, body: JSON.stringify(body), headers: { "Content-Type": "application/json" } };
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export interface ListParams {
  limit?: number;
  offset?: number;
}

export const api = {
  health: () => apiFetch<HealthResponse>("/api/health"),
  system: () => apiFetch<SystemResponse>("/api/system"),
  runDiagnostics: () => apiFetch<JobRead>("/api/system/diagnostics", { method: "POST" }),

  jobs: {
    list: (params: ListParams & { active?: boolean; type?: string } = {}) =>
      apiFetch<Page<JobRead>>(`/api/jobs${query({ ...params, active: params.active?.toString() })}`),
    get: (id: string) => apiFetch<JobRead>(`/api/jobs/${encodeURIComponent(id)}`),
    cancel: (id: string) => apiFetch<JobRead>(`/api/jobs/${encodeURIComponent(id)}`, { method: "DELETE" }),
    eventsUrl: (id: string) => `${API_BASE_URL}/api/jobs/${encodeURIComponent(id)}/events`,
  },

  projects: {
    list: (params: ListParams & { type?: ProjectType } = {}) =>
      apiFetch<Page<ProjectRead>>(`/api/projects${query({ ...params })}`),
    create: (payload: ProjectCreate) => apiFetch<ProjectRead>("/api/projects", jsonInit("POST", payload)),
    remove: (id: string) => apiFetch<void>(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" }),
  },
  characters: {
    list: (params: ListParams = {}) => apiFetch<Page<CharacterSummary>>(`/api/characters${query({ ...params })}`),
  },
  products: {
    list: (params: ListParams = {}) => apiFetch<Page<ProductSummary>>(`/api/products${query({ ...params })}`),
  },
  properties: {
    list: (params: ListParams = {}) => apiFetch<Page<PropertySummary>>(`/api/properties${query({ ...params })}`),
  },
};
