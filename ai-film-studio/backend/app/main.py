import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    ai,
    assets,
    dashboard,
    projects,
    rendering,
    scripts,
    storage,
    storyboards,
    topics,
)
from app.core.config import get_settings
from app.core.database import init_db
from app.routers import sales_prompts
from app.seed import seed_all
from app.services.ai.providers import ProviderError, ProviderUnavailable
from app.services.media.render_service import RenderError

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.seed_sample_data:
        seed_all()
    yield


app = FastAPI(
    title="AI Film Studio API",
    version="0.1.0",
    description="Local-first API for planning, generating, and rendering short business videos.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ProviderUnavailable)
async def provider_unavailable_handler(request: Request, exc: ProviderUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "code": "provider_unavailable"},
    )


@app.exception_handler(ProviderError)
async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc), "code": "provider_error"},
    )


@app.exception_handler(RenderError)
async def render_error_handler(request: Request, exc: RenderError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "code": "render_error"},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "code": "validation_error"},
    )


@app.get("/api/v1/health", tags=["system"])
def health() -> dict:
    ffmpeg = shutil.which(settings.ffmpeg_bin)
    return {
        "status": "ok",
        "app": settings.app_name,
        "mode": settings.app_mode,
        "mock_ai": settings.mock_ai,
        "render_mode": settings.render_mode,
        "ffmpeg_available": bool(ffmpeg),
        "storage": str(settings.storage_path),
        "gemma_base_url": settings.gemma_base_url,
        "gcs_enabled": settings.gcs_enabled,
        "gcs_bucket": settings.gcs_bucket,
        "gcs_prefix": settings.gcs_root,
    }


app.include_router(projects.router, prefix=settings.api_prefix)
app.include_router(topics.router, prefix=settings.api_prefix)
app.include_router(scripts.router, prefix=settings.api_prefix)
app.include_router(storyboards.router, prefix=settings.api_prefix)
app.include_router(ai.router, prefix=settings.api_prefix)
app.include_router(rendering.router, prefix=settings.api_prefix)
app.include_router(assets.router, prefix=settings.api_prefix)
app.include_router(storage.router, prefix=settings.api_prefix)
app.include_router(dashboard.router, prefix=settings.api_prefix)
app.include_router(sales_prompts.router, prefix=settings.api_prefix)
