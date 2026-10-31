"""Ops endpoints: preflight guardrails, UAT status, model catalog, prompt samples, logs."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..model_catalog import catalog, default_model
from ..models import AuditLog, ModelUsage, SyncRun, User
from ..ops_checks import run_checks
from ..security import get_current_user, require_admin

router = APIRouter(prefix="/ops", tags=["ops"])

PROMPTS_LOCAL = Path(__file__).resolve().parents[2] / "data" / "prompts" / "weekly_prompts.json"
PROMPTS_GCS = "sales-metadata/weekly_prompts.json"


def _load_prompts() -> dict:
    if PROMPTS_LOCAL.exists():
        return json.loads(PROMPTS_LOCAL.read_text(encoding="utf-8"))
    try:  # realtime fallback: read the published copy from GCS
        import google.auth
        from google.cloud import storage

        creds, _ = google.auth.default()
        blob = storage.Client(credentials=creds).bucket("kalika_enterprises").blob(PROMPTS_GCS)
        return json.loads(blob.download_as_bytes().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"prompt samples unavailable: {exc}") from exc


@router.get("/preflight")
def preflight(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Run the full guardrail/deploy check suite (admin only)."""
    return run_checks(db)


@router.post("/run-checks")
def run_checks_now(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Execute checks, persist the result to sync_runs (visible in logs), return it."""
    report = run_checks(db)
    db.add(
        SyncRun(
            job="daily_guardrail_checks",
            status="ok" if report["summary"]["ready"] else "warn",
            detail=json.dumps(report["summary"]),
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return report


@router.get("/uat")
def uat_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        until = date.fromisoformat(settings.UAT_ENABLED_UNTIL)
    except Exception:
        until = None
    days_left = (until - date.today()).days if until else None
    active = settings.UAT_ENABLED and days_left is not None and days_left >= 0
    return {
        "deploy_env": settings.DEPLOY_ENV,
        "phase": "ERP-UAT",
        "uat_active": active,
        "enabled_until": settings.UAT_ENABLED_UNTIL,
        "days_left": days_left,
        "erp_master": "prod (read-only report feed)",
        "features": [
            {"name": "ERP dispatch + orders dashboards", "status": "enabled"},
            {"name": "Sales forecast", "status": "enabled"},
            {"name": "Daily rate calculator", "status": "enabled"},
            {"name": "Feedback pipeline (wa.me send, human review)", "status": "enabled"},
            {"name": "Customer journey + stories", "status": "enabled"},
            {"name": "YouTube channel sync (Data API)", "status": "enabled"},
            {"name": "YouTube Analytics API (OAuth)", "status": "next scope"},
            {"name": "RL pattern suggestions", "status": "next scope"},
        ],
        "is_admin": (user.email or "").lower() in settings.admin_emails,
    }


@router.get("/models")
def models(user: User = Depends(get_current_user)):
    return {
        "default": default_model(),
        "human_review_required": settings.HUMAN_REVIEW_REQUIRED,
        "models": catalog(),
    }


@router.get("/prompt-samples")
def prompt_samples(task: str | None = Query(default=None), user: User = Depends(get_current_user)):
    data = _load_prompts()
    prompts = data.get("prompts", [])
    if task:
        prompts = [p for p in prompts if p.get("task") == task]
    return {
        "version": data.get("version"),
        "schedule": data.get("schedule"),
        "models": data.get("models"),
        "human_review_required": data.get("human_review_required"),
        "prompts": prompts,
    }


@router.get("/logs")
def logs(
    limit: int = Query(default=30, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recent model usage, audit and sync runs — user-checkable logs."""
    usage = db.query(ModelUsage).order_by(ModelUsage.id.desc()).limit(limit).all()
    audits = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    runs = db.query(SyncRun).order_by(SyncRun.id.desc()).limit(limit).all()

    def _r(o, fields):
        return {
            f: str(getattr(o, f, "")) if getattr(o, f, None) is not None else None for f in fields
        }

    return {
        "model_usage": [
            _r(
                u,
                [
                    "id",
                    "provider",
                    "model",
                    "task",
                    "input_tokens",
                    "output_tokens",
                    "cost_micros",
                    "latency_ms",
                    "fallback_used",
                    "created_at",
                ],
            )
            for u in usage
        ],
        "audit": [
            _r(
                a,
                [
                    "id",
                    "action",
                    "actor_user_id",
                    "resource_type",
                    "status",
                    "detail",
                    "created_at",
                ],
            )
            for a in audits
        ],
        "sync_runs": [
            _r(s, ["id", "job", "status", "detail", "started_at", "finished_at"]) for s in runs
        ],
    }
