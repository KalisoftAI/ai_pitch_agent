import type {
  Activity,
  AIResult,
  Asset,
  Category,
  CategoryInfo,
  DashboardSummary,
  HealthStatus,
  ModelInfo,
  Project,
  ProviderStatus,
  RenderJob,
  RenderLogs,
  Scene,
  Script,
  StorageObject,
  StoragePublish,
  StorageStatus,
  Storyboard,
  Topic,
  TopicSuggestion,
  UsageSummary,
} from "@/types";

export const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    let code: string | undefined;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail[0]?.msg ?? detail;
      code = body.code;
    } catch {
      // keep default message
    }
    throw new ApiError(detail, response.status, code);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export const api = {
  health: () => request<HealthStatus>("/health"),

  dashboard: () => request<DashboardSummary>("/dashboard"),
  activity: (limit = 50) => request<Activity[]>(`/activity${query({ limit })}`),

  listProjects: () => request<Project[]>("/projects"),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (payload: {
    title: string;
    category: Category;
    topic: string;
    description?: string;
    visual_style?: string;
    template?: string;
    duration_seconds?: number;
    aspect_ratio?: string;
  }) => request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) }),
  updateProject: (id: string, payload: Partial<Project>) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  updateProgress: (
    id: string,
    payload: { current_step?: string; progress?: Record<string, unknown>; status?: string },
  ) =>
    request<Project>(`/projects/${id}/progress`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  categories: () => request<CategoryInfo[]>("/topics/categories"),
  listTopics: (category?: Category) =>
    request<Topic[]>(`/topics${query({ category })}`),
  suggestTopics: (category: Category, limit = 6) =>
    request<TopicSuggestion[]>(`/topics/suggest${query({ category, limit })}`),
  createTopic: (payload: { category: Category; title: string; description?: string }) =>
    request<Topic>("/topics/custom", { method: "POST", body: JSON.stringify(payload) }),

  getScript: (projectId: string) => request<Script>(`/projects/${projectId}/script`),
  generateScript: (
    projectId: string,
    payload: { tone?: string; audience?: string; instructions?: string },
  ) =>
    request<Script>(`/projects/${projectId}/script/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateScript: (projectId: string, content: string) =>
    request<Script>(`/projects/${projectId}/script`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  regenerateParagraph: (projectId: string, paragraph_index: number, instruction = "") =>
    request<Script>(`/projects/${projectId}/script/regenerate-paragraph`, {
      method: "POST",
      body: JSON.stringify({ paragraph_index, instruction }),
    }),
  approveScript: (projectId: string, approved = true) =>
    request<Script>(`/projects/${projectId}/script/approve`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    }),

  getStoryboard: (projectId: string) =>
    request<Storyboard>(`/projects/${projectId}/storyboard`),
  generateStoryboard: (projectId: string, payload: { scene_count?: number; style?: string }) =>
    request<Storyboard>(`/projects/${projectId}/storyboard/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateScene: (projectId: string, sceneId: string, payload: Partial<Scene>) =>
    request<Scene>(`/projects/${projectId}/storyboard/scenes/${sceneId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  reorderScenes: (projectId: string, scenes: { id: string; order_index: number }[]) =>
    request<Storyboard>(`/projects/${projectId}/storyboard/scenes/reorder`, {
      method: "POST",
      body: JSON.stringify({ scenes }),
    }),
  regenerateScene: (projectId: string, sceneId: string, instruction = "") =>
    request<Scene>(`/projects/${projectId}/storyboard/scenes/${sceneId}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    }),
  approveStoryboard: (projectId: string, approved = true) =>
    request<Storyboard>(`/projects/${projectId}/storyboard/approve`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    }),

  listModels: () => request<ModelInfo[]>("/ai/models"),
  selectModel: (model_id: string) =>
    request<ModelInfo[]>("/ai/models/select", {
      method: "POST",
      body: JSON.stringify({ model_id }),
    }),
  testModel: (modelId: string) =>
    request<ProviderStatus>(`/ai/models/${modelId}/test`, { method: "POST" }),
  generateAI: (payload: {
    prompt: string;
    task?: string;
    system?: string;
    project_id?: string;
    max_tokens?: number;
  }) => request<AIResult>("/ai/generate", { method: "POST", body: JSON.stringify(payload) }),
  usage: () => request<UsageSummary>("/ai/usage"),

  createRender: (
    projectId: string,
    payload: {
      quality: string;
      include_captions: boolean;
      engine: string;
      motion_style?: string | null;
      effects?: string[];
      audio?: boolean;
      scene_patterns?: Record<string, string>;
    },
  ) =>
    request<RenderJob>(`/projects/${projectId}/renders`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listRenders: (projectId: string) => request<RenderJob[]>(`/projects/${projectId}/renders`),
  getRender: (jobId: string) => request<RenderJob>(`/renders/${jobId}`),
  getRenderLogs: (jobId: string) => request<RenderLogs>(`/renders/${jobId}/logs`),
  cancelRender: (jobId: string) =>
    request<RenderJob>(`/renders/${jobId}/cancel`, { method: "POST" }),
  publishRender: (jobId: string) =>
    request<StoragePublish>(`/renders/${jobId}/publish`, { method: "POST" }),
  renderEventsUrl: (jobId: string) => `${API_BASE}/renders/${jobId}/events`,
  previewUrl: (jobId: string) => `${API_BASE}/renders/${jobId}/preview`,
  exportUrl: (jobId: string) => `${API_BASE}/renders/${jobId}/export`,

  storageStatus: (refresh = false) =>
    request<StorageStatus>(`/storage/status${query({ refresh })}`),
  storageGallery: (limit = 50) =>
    request<StorageObject[]>(`/storage/gallery${query({ limit })}`),
  storageObjects: (prefix = "", limit = 100) =>
    request<StorageObject[]>(`/storage/objects${query({ prefix, limit })}`),

  listAssets: (params: {
    search?: string;
    media_type?: string;
    tag?: string;
    favorite?: boolean;
  } = {}) => request<Asset[]>(`/assets${query(params)}`),
  uploadAsset: (file: File, tags = "") => {
    const form = new FormData();
    form.append("file", file);
    form.append("tags", tags);
    return request<Asset>("/assets", { method: "POST", body: form });
  },
  updateAsset: (id: string, payload: { tags?: string[]; favorite?: boolean }) =>
    request<Asset>(`/assets/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteAsset: (id: string) => request<void>(`/assets/${id}`, { method: "DELETE" }),
  assetFileUrl: (asset: Asset) => `${API_BASE}/assets/${asset.id}/file`,
};
