from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import settings
from .database import init_db
from .guardrails import RequestGuardrailsMiddleware
from .routers import (
    ai_router,
    approvals_router,
    auth_router,
    campaigns_router,
    catalog_router,
    contacts_router,
    dashboard_router,
    email_router,
    erp_router,
    events_router,
    feedback_pipeline_router,
    feedback_router,
    google_analytics_router,
    google_email_router,
    governance_router,
    instore_router,
    journey_router,
    knowledge_graph_router,
    llm_router,
    marketing_companies_router,
    media_router,
    ops_router,
    sales_router,
    scheduler_router,
    social_router,
    sync_router,
    system_router,
    tally_router,
    team_router,
    templates_router,
    users_router,
    visits_router,
    voice_router,
    whatsapp_router,
)
from .routers.category_campaigns import router as category_campaigns_router

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        app.state.db_ready = True
    except Exception:  # pragma: no cover - depends on DB availability
        app.state.db_ready = False
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Sales pipeline: contacts, IMAP/SMTP, LinkedIn/Reddit hiring alerts.",
    docs_url=None if settings.ENV.lower() == "production" else "/docs",
    redoc_url=None if settings.ENV.lower() == "production" else "/redoc",
    openapi_url=None if settings.ENV.lower() == "production" else "/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(RequestGuardrailsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

api_prefix = "/api"
app.include_router(system_router, prefix=api_prefix)
app.include_router(ai_router, prefix=api_prefix)
app.include_router(auth_router, prefix=api_prefix)
app.include_router(contacts_router, prefix=api_prefix)
app.include_router(email_router, prefix=api_prefix)
app.include_router(erp_router, prefix=api_prefix)
app.include_router(sales_router, prefix=api_prefix)
app.include_router(catalog_router, prefix=api_prefix)
app.include_router(social_router, prefix=api_prefix)
app.include_router(governance_router, prefix=api_prefix)
app.include_router(llm_router, prefix=api_prefix)
app.include_router(marketing_companies_router, prefix=api_prefix)
app.include_router(media_router, prefix=api_prefix)
app.include_router(whatsapp_router, prefix=api_prefix)
app.include_router(voice_router, prefix=api_prefix)
app.include_router(templates_router, prefix=api_prefix)
app.include_router(campaigns_router, prefix=api_prefix)
app.include_router(category_campaigns_router, prefix=api_prefix)
app.include_router(scheduler_router, prefix=api_prefix)
app.include_router(feedback_router, prefix=api_prefix)
app.include_router(feedback_pipeline_router, prefix=api_prefix)
app.include_router(google_email_router, prefix=api_prefix)
app.include_router(google_analytics_router, prefix=api_prefix)
app.include_router(journey_router, prefix=api_prefix)
app.include_router(ops_router, prefix=api_prefix)
app.include_router(events_router, prefix=api_prefix)
app.include_router(dashboard_router, prefix=api_prefix)
app.include_router(tally_router, prefix=api_prefix)
app.include_router(instore_router, prefix=api_prefix)
app.include_router(knowledge_graph_router, prefix=api_prefix)
app.include_router(team_router, prefix=api_prefix)
app.include_router(visits_router, prefix=api_prefix)
app.include_router(users_router, prefix=api_prefix)
app.include_router(sync_router, prefix=api_prefix)
app.include_router(approvals_router, prefix=api_prefix)


@app.get("//api/email/google/callback", include_in_schema=False)
def gmail_oauth_callback_bridge(request: Request):
    """Bridge the OAuth client's registered double-slash callback to the app route.

    The existing Google OAuth web client has the callback registered as
    ``https://<host>//api/email/google/callback``. The token exchange must use
    that exact URI, so redirect the browser to the canonical single-slash path
    while preserving the OAuth code and state query parameters.
    """
    query = request.url.query
    target = "/api/email/google/callback"
    if query:
        target = f"{target}?{query}"
    return RedirectResponse(target, status_code=307)


@app.get("/", include_in_schema=False)
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": settings.PROJECT_NAME, "docs": "/docs"}


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
