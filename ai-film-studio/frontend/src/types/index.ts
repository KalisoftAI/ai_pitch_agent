export type Category = "business-tips" | "erp-walkthrough" | "financial-education";

export interface CategoryInfo {
  id: Category;
  label: string;
  description?: string;
  project_count?: number;
}

export interface Project {
  id: string;
  title: string;
  category: Category;
  topic: string;
  description: string;
  visual_style: string;
  template: string;
  duration_seconds: number;
  aspect_ratio: string;
  status: string;
  progress: Record<string, unknown>;
  current_step: string;
  created_at: string;
  updated_at: string;
  script?: Script | null;
  storyboard?: Storyboard | null;
}

export interface Script {
  id: string;
  project_id: string;
  content: string;
  approved: boolean;
  version: number;
  updated_at: string;
}

export interface Scene {
  id: string;
  storyboard_id: string;
  order_index: number;
  title: string;
  narration: string;
  visual_prompt: string;
  duration_seconds: number;
  transition: string;
  asset_id: string | null;
  status: string;
}

export interface Storyboard {
  id: string;
  project_id: string;
  approved: boolean;
  scenes: Scene[];
  updated_at: string;
}

export interface Topic {
  id: string;
  category: Category;
  title: string;
  description: string;
  is_custom: boolean;
  created_at: string;
}

export interface TopicSuggestion {
  title: string;
  description: string;
  category: Category;
}

export interface ModelInfo {
  id: string;
  provider: string;
  label: string;
  task: string;
  local: boolean;
  configured: boolean;
  selected: boolean;
  description: string;
}

export interface ProviderStatus {
  provider: string;
  model: string;
  configured: boolean;
  reachable: boolean;
  message: string;
  latency_ms: number | null;
}

export interface AIResult {
  text: string;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  cached: boolean;
}

export interface UsageBucket {
  provider: string;
  model: string;
  requests: number;
  total_tokens: number;
  estimated_cost: number;
}

export interface UsageSummary {
  total_requests: number;
  total_tokens: number;
  estimated_cost: number;
  budget_usd: number;
  budget_used_pct: number;
  selected_model: string;
  by_model: UsageBucket[];
}

export interface RenderJob {
  id: string;
  project_id: string;
  status: string;
  stage: string;
  progress: number;
  logs: string;
  preview_path: string | null;
  export_path: string | null;
  error: string | null;
  options: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RenderLogs {
  job_id: string;
  status: string;
  logs: string[];
}

export interface StorageStatus {
  enabled: boolean;
  available: boolean;
  bucket: string;
  prefix: string;
  project: string;
  message: string;
}

export interface StorageObject {
  name: string;
  uri: string;
  size: number;
  content_type?: string | null;
  updated?: string | null;
  metadata?: Record<string, unknown>;
}

export interface StoragePublish {
  bucket: string;
  prefix: string;
  folder: string;
  objects: StorageObject[];
  manifest: StorageObject;
  published_at: string;
}

export interface Asset {
  id: string;
  filename: string;
  original_name: string;
  media_type: string;
  content_type: string;
  size_bytes: number;
  tags: string[];
  favorite: boolean;
  created_at: string;
  url: string;
}

export interface Activity {
  id: string;
  project_id: string | null;
  kind: string;
  message: string;
  created_at: string;
}

export interface DashboardSummary {
  projects_total: number;
  projects_in_progress: number;
  renders_active: number;
  renders_completed: number;
  assets_total: number;
  usage: UsageSummary;
  recent_projects: Project[];
  recent_activity: Activity[];
  categories: CategoryInfo[];
}

export interface HealthStatus {
  status: string;
  app: string;
  mode: string;
  mock_ai: boolean;
  render_mode: string;
  ffmpeg_available: boolean;
  storage: string;
  gemma_base_url: string;
  gcs_enabled?: boolean;
  gcs_bucket?: string;
  gcs_prefix?: string;
}
