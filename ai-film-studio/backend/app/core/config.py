from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AI Film Studio"
    app_mode: str = "development"
    api_prefix: str = "/api/v1"
    mock_ai: bool = True
    seed_sample_data: bool = True
    render_mode: str = "motion"
    database_url: str = "sqlite:///./storage/ai_film_studio.db"
    storage_dir: str = "./storage"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    gemma_model_id: str = "gemma-4-12b-it-qat-q4_0"
    gemma_base_url: str = "http://127.0.0.1:8081/v1"
    gemma_api_key: str = "local"
    gemma_model_path: str = "./storage/models/gemma-4-12b-it-qat-q4_0/gemma-4-12b-it-qat-q4_0.gguf"

    gemini_api_key: str = ""
    gemini_flash_lite_model: str = "gemini-2.5-flash-lite"
    gemini_flash_model: str = "gemini-2.5-flash"
    gemini_pro_model: str = "gemini-2.5-pro"

    anthropic_api_key: str = ""
    claude_opus_model: str = "claude-opus-4-5"

    ai_cache_ttl_seconds: int = 3600
    ai_max_output_tokens: int = 2048
    ai_max_retries: int = 2
    ai_monthly_budget_usd: float = 25.0

    ffmpeg_bin: str = "ffmpeg"
    preview_width: int = 640
    preview_height: int = 360
    export_width: int = 1280
    export_height: int = 720

    motion_renderer_dir: str = "./renderer"
    motion_template: str = "default"
    motion_chrome_path: str = ""
    motion_fps: int = 24
    motion_workers: int = 2
    motion_timeout_seconds: int = 3600
    motion_ai_direction: bool = True
    motion_ai_timeout_seconds: int = 25
    motion_fallback_to_cards: bool = True
    motion_audio: bool = True
    motion_audio_sr: int = 48000
    motion_effects: str = "grain,vignette,particles"

    gcs_enabled: bool = False
    gcs_bucket: str = "sales-crm"
    gcs_prefix: str = "marketing-videos"
    gcs_project: str = ""
    gcs_auto_publish: bool = True
    gcs_timeout_seconds: int = 60

    @field_validator("app_mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"development", "live"}:
            raise ValueError("APP_MODE must be development or live")
        return value

    @field_validator("render_mode")
    @classmethod
    def validate_render_mode(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"motion", "ffmpeg", "simulated"}:
            raise ValueError("RENDER_MODE must be motion, ffmpeg or simulated")
        return value

    @field_validator("motion_template")
    @classmethod
    def validate_motion_template(cls, value: str) -> str:
        value = value.strip().lower() or "default"
        if not all(char.isalnum() or char in "-_" for char in value):
            raise ValueError("MOTION_TEMPLATE must contain only letters, digits, - or _")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.frontend_origins.split(",") if item.strip()]

    @property
    def default_motion_effects(self) -> list[str]:
        return [item.strip() for item in self.motion_effects.split(",") if item.strip()]

    @property
    def gcs_root(self) -> str:
        return self.gcs_prefix.strip().strip("/")

    @property
    def renderer_path(self) -> Path:
        path = Path(self.motion_renderer_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def database_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            raw = self.database_url.replace("sqlite:///", "", 1)
            path = Path(raw)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            return path.resolve()
        return PROJECT_ROOT / "storage" / "ai_film_studio.db"

    def find_chrome(self) -> str | None:
        import os
        import shutil

        explicit = self.motion_chrome_path or os.environ.get("PLAYWRIGHT_CHROME", "")
        if explicit and Path(explicit).exists():
            return explicit
        candidates = [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/chromium"),
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        for name in ("chrome", "google-chrome", "chromium", "msedge"):
            found = shutil.which(name)
            if found:
                return found
        return None

    def ensure_dirs(self) -> None:
        for name in ("projects", "assets", "previews", "exports", "temp", "models", "audio"):
            (self.storage_path / name).mkdir(parents=True, exist_ok=True)

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
