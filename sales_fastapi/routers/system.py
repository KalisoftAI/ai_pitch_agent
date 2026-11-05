from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request

from ..config import settings
from ..scheduler import scheduler_service
from ..security import get_current_user
from ..services import GCSStorage

router = APIRouter(tags=["system"])


def _redis_ping() -> str:
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        client.ping()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {exc}"


@router.get("/config")
def public_config():
    """Public client config (no secrets)."""
    deploy_env = settings.DEPLOY_ENV.lower()
    try:
        uat_active = settings.UAT_ENABLED and date.fromisoformat(settings.UAT_ENABLED_UNTIL) >= date.today()
    except ValueError:
        uat_active = False
    graph_review_enabled = (
        settings.ENV.lower() not in {"prod", "production"}
        and deploy_env in {"dev", "development", "preprod", "stage", "staging", "uat"}
        and (
            deploy_env not in {"stage", "staging", "uat"}
            or uat_active
        )
    )
    return {
        "project_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "env": settings.ENV,
        "deploy_env": settings.DEPLOY_ENV,
        "knowledge_graph_review_enabled": graph_review_enabled,
        "google_client_id": settings.GOOGLE_CLIENT_ID if settings.google_signin_configured else "",
        "google_gmail_oauth_configured": settings.google_gmail_oauth_configured,
        "dev_mode": settings.AUTH_DEV_MODE,
    }


@router.get("/health")
def health(request: Request):
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "env": settings.ENV,
        "time": datetime.now(timezone.utc).isoformat(),
        "database": "ok" if request.app.state.db_ready else "degraded",
        "redis": _redis_ping(),
        "gcs_available": GCSStorage().available,
        "google_signin_configured": settings.google_signin_configured,
        "google_gmail_oauth_configured": settings.google_gmail_oauth_configured,
        "dev_mode": settings.AUTH_DEV_MODE,
    }


@router.get("/integrations")
def integrations(user=Depends(get_current_user)):
    return {
        "gcs": {
            "bucket": settings.GCS_BUCKET_CONTACTS,
            "path": settings.GCS_PATH_CONTACTS,
            "available": GCSStorage().available,
        },
        "redis_url": settings.redis_url.split("@")[-1],
        "gemma_model": settings.GEMMA_MODEL,
        "whatsapp": bool(settings.WHATSAPP_API_KEY),
        "linkedin": bool(settings.LINKEDIN_CLIENT_ID),
        "reddit": bool(settings.REDDIT_CLIENT_ID),
        "youtube": bool(settings.YOUTUBE_API_KEY),
        "smtp": bool(settings.SMTP_HOST),
        "imap": bool(settings.IMAP_HOST),
        "scheduler_backend": "redis" if settings.REDIS_URL else "in-memory",
    }


@router.post("/cron/run")
def run_cron(user=Depends(get_current_user)):
    """Trigger the scheduled pipeline tasks."""
    tasks = [t["name"] for t in scheduler_service.registered_tasks()]
    queued = scheduler_service.enqueue_standard_tasks(user_id=getattr(user, "id", None))
    return {
        "tasks": tasks,
        "queued_count": len(queued),
        "backend": scheduler_service.backend_status(),
    }
