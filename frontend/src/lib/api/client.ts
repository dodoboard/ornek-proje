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
export type ProductRead = Schemas["ProductRead"];
export type ProductCreate = Schemas["ProductCreate"];
export type ProductCutoutRequest = Schemas["ProductCutoutRequest"];
export type ProductSceneRequest = Schemas["ProductSceneRequest"];
export type AssetLinkRead = Schemas["AssetLinkRead"];
export type ScriptGenerateRequest = Schemas["ScriptGenerateRequest"];
export type ScriptRead = Schemas["ScriptRead"];
export type StoryboardRead = Schemas["StoryboardRead"];
export type ShotRead = Schemas["ShotRead"];
export type ShotUpdate = Schemas["ShotUpdate"];
export type ShotCreate = Schemas["ShotCreate"];
export type PropertySummary = Schemas["PropertySummary"];
export type JobRead = Schemas["JobRead"];
export type JobStatus = JobRead["status"];
export type WorkerStatus = Schemas["WorkerStatus"];
export type ModelsResponse = Schemas["ModelsResponse"];
export type KindModels = Schemas["KindModels"];
export type ProviderInfo = Schemas["ProviderInfo"];
export type ProviderKind = Schemas["ProviderKind"];
export type ProviderStatus = Schemas["ProviderStatus"];
export type Preferences = Schemas["PreferencesRead"];
export type PreferencesUpdate = Schemas["PreferencesUpdate"];
export type PerformanceProfile = Schemas["PerformanceProfile"];
export type AssetRead = Schemas["AssetRead"];
export type ImageGenerateRequest = Schemas["ImageGenerateRequest"];
export type ImageEditRequest = Schemas["ImageEditRequest"];
export type VideoGenerateRequest = Schemas["VideoGenerateRequest"];
export type GenerationRead = Schemas["GenerationRead"];
export type CharacterRead = Schemas["CharacterRead"];
export type CharacterCreate = Schemas["CharacterCreate"];
export type CharacterUpdate = Schemas["CharacterUpdate"];
export type CharacterBible = Schemas["CharacterBibleRead"];
export type CharacterBibleUpdate = Schemas["CharacterBibleUpdate"];
export type CharacterGenerateRequest = Schemas["CharacterGenerateRequest"];
export type CharacterPurpose = CharacterGenerateRequest["purpose"];
export type PromptPreview = Schemas["PromptPreview"];
export type ConsentCreate = Schemas["ConsentCreate"];
export type ConsentRead = Schemas["ConsentRead"];
export type ViewRole = "canonical" | "front" | "three_quarter" | "full_body";

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

  assets: {
    upload: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiFetch<AssetRead>("/api/assets", { method: "POST", body: form });
    },
    contentUrl: (id: string) => `${API_BASE_URL}/api/assets/${encodeURIComponent(id)}/content`,
    thumbnailUrl: (id: string) => `${API_BASE_URL}/api/assets/${encodeURIComponent(id)}/thumbnail`,
  },
  generate: {
    image: (body: ImageGenerateRequest) => apiFetch<JobRead>("/api/generate/image", jsonInit("POST", body)),
    imageEdit: (body: ImageEditRequest) => apiFetch<JobRead>("/api/generate/image-edit", jsonInit("POST", body)),
    video: (body: VideoGenerateRequest) => apiFetch<JobRead>("/api/generate/video", jsonInit("POST", body)),
  },
  generations: {
    list: (
      params: ListParams & { kind?: string; project_id?: string; character_id?: string; product_id?: string } = {},
    ) =>
      apiFetch<Page<GenerationRead>>(`/api/generations${query({ ...params })}`),
    get: (id: string) => apiFetch<GenerationRead>(`/api/generations/${encodeURIComponent(id)}`),
  },

  models: {
    list: () => apiFetch<ModelsResponse>("/api/models"),
  },
  settings: {
    get: () => apiFetch<Preferences>("/api/settings"),
    update: (patch: PreferencesUpdate) => apiFetch<Preferences>("/api/settings", jsonInit("PATCH", patch)),
  },

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
  consents: {
    create: (body: ConsentCreate) => apiFetch<ConsentRead>("/api/consents", jsonInit("POST", body)),
  },
  characters: {
    list: (params: ListParams = {}) => apiFetch<Page<CharacterSummary>>(`/api/characters${query({ ...params })}`),
    get: (id: string) => apiFetch<CharacterRead>(`/api/characters/${encodeURIComponent(id)}`),
    create: (body: CharacterCreate) => apiFetch<CharacterRead>("/api/characters", jsonInit("POST", body)),
    update: (id: string, body: CharacterUpdate) =>
      apiFetch<CharacterRead>(`/api/characters/${encodeURIComponent(id)}`, jsonInit("PATCH", body)),
    remove: (id: string) => apiFetch<void>(`/api/characters/${encodeURIComponent(id)}`, { method: "DELETE" }),
    attachAsset: (id: string, assetId: string, role: string) =>
      apiFetch<CharacterRead>(
        `/api/characters/${encodeURIComponent(id)}/assets`,
        jsonInit("POST", { asset_id: assetId, role }),
      ),
    detachAsset: (id: string, assetId: string) =>
      apiFetch<void>(`/api/characters/${encodeURIComponent(id)}/assets/${encodeURIComponent(assetId)}`, {
        method: "DELETE",
      }),
    bible: (id: string) => apiFetch<CharacterBible>(`/api/characters/${encodeURIComponent(id)}/bible`),
    updateBible: (id: string, body: CharacterBibleUpdate) =>
      apiFetch<CharacterBible>(`/api/characters/${encodeURIComponent(id)}/bible`, jsonInit("PATCH", body)),
    generate: (id: string, body: CharacterGenerateRequest) =>
      apiFetch<JobRead>(`/api/characters/${encodeURIComponent(id)}/generate`, jsonInit("POST", body)),
    previewPrompt: (id: string, body: CharacterGenerateRequest) =>
      apiFetch<PromptPreview>(`/api/characters/${encodeURIComponent(id)}/prompt-preview`, jsonInit("POST", body)),
    setView: (id: string, role: ViewRole, assetId: string) =>
      apiFetch<CharacterRead>(
        `/api/characters/${encodeURIComponent(id)}/views/${role}`,
        jsonInit("PUT", { asset_id: assetId }),
      ),
  },
  storyboards: {
    generateScript: (projectId: string, body: ScriptGenerateRequest) =>
      apiFetch<JobRead>(`/api/projects/${encodeURIComponent(projectId)}/script`, jsonInit("POST", body)),
    scripts: (projectId: string) => apiFetch<ScriptRead[]>(`/api/projects/${encodeURIComponent(projectId)}/scripts`),
    latest: (projectId: string) =>
      apiFetch<StoryboardRead>(`/api/projects/${encodeURIComponent(projectId)}/storyboard`),
    addShot: (storyboardId: string, body: ShotCreate) =>
      apiFetch<StoryboardRead>(`/api/storyboards/${encodeURIComponent(storyboardId)}/shots`, jsonInit("POST", body)),
    reorder: (storyboardId: string, shotIds: string[]) =>
      apiFetch<StoryboardRead>(
        `/api/storyboards/${encodeURIComponent(storyboardId)}/order`,
        jsonInit("PUT", { shot_ids: shotIds }),
      ),
    updateShot: (shotId: string, body: ShotUpdate) =>
      apiFetch<ShotRead>(`/api/shots/${encodeURIComponent(shotId)}`, jsonInit("PATCH", body)),
    deleteShot: (shotId: string) => apiFetch<void>(`/api/shots/${encodeURIComponent(shotId)}`, { method: "DELETE" }),
  },
  products: {
    list: (params: ListParams = {}) => apiFetch<Page<ProductSummary>>(`/api/products${query({ ...params })}`),
    get: (id: string) => apiFetch<ProductRead>(`/api/products/${encodeURIComponent(id)}`),
    create: (body: ProductCreate) => apiFetch<ProductRead>("/api/products", jsonInit("POST", body)),
    remove: (id: string) => apiFetch<void>(`/api/products/${encodeURIComponent(id)}`, { method: "DELETE" }),
    attachAsset: (id: string, assetId: string, role: string) =>
      apiFetch<ProductRead>(`/api/products/${encodeURIComponent(id)}/assets`, jsonInit("POST", { asset_id: assetId, role })),
    cutout: (id: string, body: ProductCutoutRequest) =>
      apiFetch<JobRead>(`/api/products/${encodeURIComponent(id)}/cutout`, jsonInit("POST", body)),
    scene: (id: string, body: ProductSceneRequest) =>
      apiFetch<JobRead>(`/api/products/${encodeURIComponent(id)}/scene`, jsonInit("POST", body)),
  },
  properties: {
    list: (params: ListParams = {}) => apiFetch<Page<PropertySummary>>(`/api/properties${query({ ...params })}`),
  },
};
