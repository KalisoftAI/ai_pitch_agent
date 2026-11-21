from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal["business-tips", "erp-walkthrough", "financial-education"]

CATEGORY_LABELS: dict[str, str] = {
    "business-tips": "Business Tips",
    "erp-walkthrough": "ERP & Production App Walkthroughs",
    "financial-education": "Financial Education",
}


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    category: Category
    topic: str = Field(min_length=2, max_length=300)
    description: str = ""
    visual_style: str = "cinematic"
    template: str = "insight"
    duration_seconds: int = Field(default=45, ge=15, le=300)
    aspect_ratio: str = "16:9"


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    category: Category | None = None
    topic: str | None = Field(default=None, min_length=2, max_length=300)
    description: str | None = None
    visual_style: str | None = None
    template: str | None = None
    duration_seconds: int | None = Field(default=None, ge=15, le=300)
    aspect_ratio: str | None = None
    status: str | None = None
    current_step: str | None = None
    progress: dict[str, Any] | None = None


class ProjectProgressUpdate(BaseModel):
    current_step: str | None = None
    progress: dict[str, Any] = Field(default_factory=dict)
    status: str | None = None


class SceneRead(ORMModel):
    id: str
    storyboard_id: str
    order_index: int
    title: str
    narration: str
    visual_prompt: str
    duration_seconds: float
    transition: str
    asset_id: str | None
    status: str


class StoryboardRead(ORMModel):
    id: str
    project_id: str
    approved: bool
    scenes: list[SceneRead] = Field(default_factory=list)
    updated_at: datetime


class ScriptRead(ORMModel):
    id: str
    project_id: str
    content: str
    approved: bool
    version: int
    updated_at: datetime


class ProjectRead(ORMModel):
    id: str
    title: str
    category: str
    topic: str
    description: str
    visual_style: str
    template: str
    duration_seconds: int
    aspect_ratio: str
    status: str
    progress: dict[str, Any] = Field(default_factory=dict)
    current_step: str
    created_at: datetime
    updated_at: datetime
    script: ScriptRead | None = None
    storyboard: StoryboardRead | None = None


class TopicRead(ORMModel):
    id: str
    category: str
    title: str
    description: str
    is_custom: bool
    created_at: datetime


class TopicSuggestion(BaseModel):
    title: str
    description: str
    category: str


class CustomTopicCreate(BaseModel):
    category: Category
    title: str = Field(min_length=3, max_length=300)
    description: str = ""


class ScriptGenerateRequest(BaseModel):
    tone: str = "confident"
    audience: str = "small business owners"
    instructions: str = ""


class ScriptUpdate(BaseModel):
    content: str = Field(min_length=1)


class ParagraphRegenerateRequest(BaseModel):
    paragraph_index: int = Field(ge=0)
    instruction: str = ""


class ApproveRequest(BaseModel):
    approved: bool = True


class StoryboardGenerateRequest(BaseModel):
    scene_count: int = Field(default=6, ge=3, le=12)
    style: str | None = None


class SceneUpdate(BaseModel):
    title: str | None = None
    narration: str | None = None
    visual_prompt: str | None = None
    duration_seconds: float | None = Field(default=None, ge=1, le=30)
    transition: str | None = None
    asset_id: str | None = None
    status: str | None = None


class SceneOrderItem(BaseModel):
    id: str
    order_index: int


class SceneReorderRequest(BaseModel):
    scenes: list[SceneOrderItem]


class SceneRegenerateRequest(BaseModel):
    instruction: str = ""


class ModelInfo(BaseModel):
    id: str
    provider: str
    label: str
    task: str
    local: bool
    configured: bool
    selected: bool = False
    description: str = ""


class ProviderStatus(BaseModel):
    provider: str
    model: str
    configured: bool
    reachable: bool
    message: str
    latency_ms: int | None = None


class ModelSelectRequest(BaseModel):
    model_id: str


class AIGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    task: str = "short-draft"
    system: str = ""
    project_id: str | None = None
    max_tokens: int | None = Field(default=None, ge=32, le=8192)


class AIResult(BaseModel):
    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    cached: bool


class UsageBucket(BaseModel):
    provider: str
    model: str
    requests: int
    total_tokens: int
    estimated_cost: float


class UsageSummary(BaseModel):
    total_requests: int
    total_tokens: int
    estimated_cost: float
    budget_usd: float
    budget_used_pct: float
    selected_model: str
    by_model: list[UsageBucket]


class RenderCreate(BaseModel):
    quality: Literal["preview", "export", "both"] = "both"
    include_captions: bool = True
    engine: Literal["motion", "cards"] = "motion"
    motion_style: str | None = None
    effects: list[str] = Field(default_factory=list)
    audio: bool = True
    scene_patterns: dict[str, str] = Field(default_factory=dict)
    template: str = "default"

    @field_validator("template")
    @classmethod
    def validate_template(cls, value: str) -> str:
        value = (value or "").strip().lower() or "default"
        if not all(char.isalnum() or char in "-_" for char in value):
            raise ValueError("template must contain only letters, digits, - or _")
        return value


class RenderRead(ORMModel):
    id: str
    project_id: str
    status: str
    stage: str
    progress: int
    logs: str
    preview_path: str | None
    export_path: str | None
    error: str | None
    options: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RenderLogs(BaseModel):
    job_id: str
    status: str
    logs: list[str]


class AssetRead(ORMModel):
    id: str
    filename: str
    original_name: str
    media_type: str
    content_type: str
    size_bytes: int
    tags: list[str] = Field(default_factory=list)
    favorite: bool
    created_at: datetime
    url: str = ""


class AssetUpdate(BaseModel):
    tags: list[str] | None = None
    favorite: bool | None = None


class ActivityRead(ORMModel):
    id: str
    project_id: str | None
    kind: str
    message: str
    created_at: datetime


class DashboardSummary(BaseModel):
    projects_total: int
    projects_in_progress: int
    renders_active: int
    renders_completed: int
    assets_total: int
    usage: UsageSummary
    recent_projects: list[ProjectRead]
    recent_activity: list[ActivityRead]
    categories: list[dict[str, Any]]


class StorageStatusRead(BaseModel):
    enabled: bool
    available: bool
    bucket: str
    prefix: str
    project: str
    message: str


class StorageObjectRead(BaseModel):
    name: str
    uri: str
    size: int = 0
    content_type: str | None = None
    updated: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoragePublishRead(BaseModel):
    bucket: str
    prefix: str
    folder: str
    objects: list[StorageObjectRead] = Field(default_factory=list)
    manifest: StorageObjectRead
    published_at: str
