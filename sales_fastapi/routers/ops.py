"""Ops endpoints: preflight guardrails, UAT status, model catalog, prompt samples, logs."""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..llm.guardrails import scan_prompt, validate_output
from ..llm.providers import (
    EchoProvider,
    GeminiProvider,
    GemmaProvider,
    OllamaProvider,
    log_llm_error,
    tag_llm_error,
)
from ..llm.router import estimate_cost_micros
from ..model_catalog import catalog, default_model
from ..models import (
    AuditLog,
    ModelUsage,
    Product,
    ProductRate,
    PromptReview,
    SyncRun,
    User,
)
from ..ops_checks import run_checks
from ..security import get_current_user, is_admin_user, require_admin

router = APIRouter(prefix="/ops", tags=["ops"])

PROMPTS_LOCAL = Path(__file__).resolve().parents[2] / "data" / "prompts" / "weekly_prompts.json"
PROMPTS_GCS = "sales-metadata/weekly_prompts.json"

_CHAT_SYSTEM = (
    "You are the Kalika Enterprises daily sales and rate copilot. Answer briefly and "
    "practically for an Indian B2B packaging business. Use INR, kg, microns and mm "
    "where relevant. For film costing use: net weight = width(m) x length(m) x "
    "micron/1000 x density; gross weight adds waste; price = (material + conversion) "
    "x (1 + margin). Never invent live ERP or polymer rates. If data is not provided, "
    "say exactly what is missing and ask for the inputs."
)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatAttachment(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    content_type: str = Field(default="image/png", max_length=80)
    size: int = Field(default=0, ge=0, le=2_000_000)


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    model: str = Field(default="", max_length=128)
    history: list[ChatTurn] = Field(default_factory=list)
    attachment: ChatAttachment | None = None


class PromptReviewIn(BaseModel):
    prompt_id: str = Field(..., min_length=1, max_length=16)
    prompt_version: str = Field(default="", max_length=32)
    task: str = Field(default="", max_length=64)
    comment: str = Field(..., min_length=1, max_length=2000)
    proposed_change: str = Field(default="", max_length=4000)


class PromptReviewDecision(BaseModel):
    status: Literal["approved", "rejected"]
    review_note: str = Field(default="", max_length=2000)


_OLLAMA_CACHE: dict[str, float | bool] = {"checked": 0.0, "ok": False}


def _ollama_reachable() -> bool:
    if time.monotonic() - float(_OLLAMA_CACHE["checked"]) < 30:
        return bool(_OLLAMA_CACHE["ok"])
    try:
        import httpx

        response = httpx.get(f"{settings.LLM_LOCAL_BASE_URL.rstrip('/')}/api/tags", timeout=0.8)
        ok = response.status_code == 200
    except Exception:  # noqa: BLE001 - a missing local runtime is a normal state
        ok = False
    _OLLAMA_CACHE.update(checked=time.monotonic(), ok=ok)
    return ok


def _model_available(provider: str) -> bool:
    if provider == "ollama":
        return _ollama_reachable()
    if provider in {"gemini", "gemma"}:
        return bool(settings.GEMINI_API_KEY)
    if provider == "echo":
        return True
    return False


def _provider_for(model_id: str):
    catalog_ids = {item["id"]: item["provider"] for item in catalog()}
    provider = catalog_ids.get(model_id)
    if provider == "ollama":
        return OllamaProvider()
    if provider == "gemma":
        return GemmaProvider()
    if provider == "gemini":
        return GeminiProvider()
    if provider == "echo" or model_id == "echo":
        return EchoProvider()
    return None


def _chat_chain(requested: str) -> list[str]:
    chain: list[str] = []
    for model_id in (
        requested,
        settings.LLM_CHAT_LOCAL_MODEL,
        settings.LLM_LOCAL_MODEL,
        settings.LLM_GEMMA_MODEL,
        settings.LLM_CLOUD_FLASH_MODEL,
        "echo",
    ):
        if model_id and model_id not in chain:
            chain.append(model_id)
    return chain


def _chat_prompt(
    message: str,
    history: list[ChatTurn],
    attachment: ChatAttachment | None = None,
) -> str:
    lines: list[str] = []
    for turn in history[-10:]:
        speaker = "User" if turn.role == "user" else "Assistant"
        lines.append(f"{speaker}: {turn.content}")
    lines.append(f"User: {message}")
    if attachment:
        lines.append(
            f"User attached: {attachment.name} ({attachment.content_type}, "
            f"{attachment.size} bytes). Treat it as a logo or reference image. "
            "Ask for any visual details you cannot inspect."
        )
    lines.append("Assistant:")
    return "\n".join(lines)


def _rate_context(db: Session, user: User) -> str:
    rows = (
        db.query(ProductRate, Product)
        .join(Product, Product.id == ProductRate.product_id)
        .filter(
            ProductRate.status == "approved",
            ProductRate.user_id.in_([0, user.id]),
        )
        .order_by(ProductRate.effective_date.desc(), ProductRate.id.desc())
        .limit(12)
        .all()
    )
    if not rows:
        return "No approved catalogue rates are available in the app yet."
    lines = [
        f"- {product.name} ({product.code or 'no code'}): "
        f"INR {rate.rate:g}/{rate.unit}, effective {rate.effective_date or 'not set'}"
        for rate, product in rows
    ]
    return "Current approved catalogue rates from the app (do not invent others):\n" + "\n".join(
        lines
    )


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
        "is_admin": is_admin_user(user),
    }


@router.get("/models")
def models(user: User = Depends(get_current_user)):
    chat_default = (
        settings.LLM_GEMMA_MODEL if settings.GEMINI_API_KEY else settings.LLM_CHAT_LOCAL_MODEL
    )
    items = catalog()
    for item in items:
        item["available"] = _model_available(item["provider"])
        item["is_default"] = item["id"] == chat_default
    return {
        "default": default_model(),
        "chat_default": chat_default,
        "human_review_required": settings.HUMAN_REVIEW_REQUIRED,
        "providers": {
            "ollama": _ollama_reachable(),
            "gemini": bool(settings.GEMINI_API_KEY),
            "gemma": bool(settings.GEMINI_API_KEY),
            "echo": True,
        },
        "models": items,
    }


@router.post("/chat")
def chat(
    payload: ChatIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Daily rate chat for signed-in Kalika users, with an optional model override."""
    prompt = _chat_prompt(payload.message, payload.history, payload.attachment)
    report = scan_prompt(
        prompt,
        max_chars=settings.LLM_MAX_INPUT_CHARS,
        redact_pii=True,
    )
    if not report.allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Message blocked by guardrails: {', '.join(report.reasons)}",
        )

    system_prompt = f"{_CHAT_SYSTEM}\n\n{_rate_context(db, user)}"
    attempts: list[dict] = []
    fallback_used = False
    for model_id in _chat_chain(payload.model):
        provider = _provider_for(model_id)
        if provider is None:
            attempts.append({"model": model_id, "status": "unknown_model"})
            fallback_used = True
            continue
        if not provider.available or not _model_available(provider.name):
            attempts.append({"model": model_id, "status": "unavailable", "tag": "llm:unavailable"})
            fallback_used = True
            continue
        try:
            result = provider.generate(
                prompt=report.sanitized,
                system=system_prompt,
                model=model_id,
                max_output_tokens=512,
                temperature=0.3,
            )
        except Exception as exc:  # noqa: BLE001 - try the next model in the chain
            tag = tag_llm_error(exc)
            log_llm_error(tag, model=model_id, task="daily_rate_chat", detail=str(exc))
            attempts.append(
                {"model": model_id, "status": f"error:{type(exc).__name__}", "tag": tag}
            )
            fallback_used = True
            continue

        output_report = validate_output(
            result.text,
            max_chars=settings.LLM_MAX_OUTPUT_CHARS,
        )
        if not output_report.allowed:
            attempts.append({"model": model_id, "status": "invalid_output"})
            fallback_used = True
            continue

        cost = estimate_cost_micros(result.model, result.input_tokens, result.output_tokens)
        attempts.append({"model": result.model, "status": "ok"})
        db.add(
            ModelUsage(
                user_id=user.id,
                task="daily_rate_chat",
                tier="chat",
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_micros=cost,
                latency_ms=result.latency_ms,
                fallback_used=fallback_used,
            )
        )
        log_event(
            db,
            action="llm.daily_rate_chat",
            actor_user_id=user.id,
            resource_type="llm_chat",
            resource_id=result.model,
            status="ok",
            detail={
                "requested": payload.model or settings.LLM_CHAT_LOCAL_MODEL,
                "attachment": payload.attachment.name if payload.attachment else None,
            },
            commit=False,
        )
        db.commit()
        notice = ""
        reply = result.text
        if result.provider == "echo":
            notice = (
                "No live model is reachable. Start Ollama and pull "
                f"{settings.LLM_CHAT_LOCAL_MODEL}, or set GEMINI_API_KEY for cloud Gemma/Gemini; "
                "this is the offline rate fallback."
            )
            reply = (
                "The live model is offline, but the daily rate assistant can still help.\n\n"
                "Film formula: net weight = width(m) x length(m) x micron/1000 x density. "
                "Add waste %, then price = (material + conversion) x (1 + margin).\n\n"
                f"{_rate_context(db, user)}\n\n"
                "Open Catalogue & rates to run a full quote, or start Ollama with "
                f"{settings.LLM_CHAT_LOCAL_MODEL} / configure GEMINI_API_KEY and ask again "
                "for model-generated advice."
            )
        return {
            "reply": reply,
            "provider": result.provider,
            "model": result.model,
            "requested_model": payload.model or settings.LLM_CHAT_LOCAL_MODEL,
            "fallback_used": fallback_used,
            "error_tags": [a["tag"] for a in attempts if a.get("tag")],
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_micros": cost,
            "guardrails": {
                "prompt": report.as_dict(),
                "output": output_report.as_dict(),
            },
            "attempts": attempts,
            "attachment": payload.attachment.name if payload.attachment else None,
            "notice": notice,
        }

    raise HTTPException(status_code=503, detail=f"No model could answer. Attempts: {attempts}")


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


def _prompt_review_item(row: PromptReview) -> dict:
    return {
        "id": row.id,
        "prompt_id": row.prompt_id,
        "prompt_version": row.prompt_version,
        "task": row.task,
        "comment": row.comment,
        "proposed_change": row.proposed_change,
        "status": row.status,
        "submitted_by": row.submitted_by,
        "submitted_by_id": row.submitted_by_id,
        "reviewed_by": row.reviewed_by,
        "review_note": row.review_note,
        "reviewed_at": str(row.reviewed_at) if row.reviewed_at else None,
        "created_at": str(row.created_at) if row.created_at else None,
    }


@router.get("/prompt-reviews")
def prompt_reviews(
    status: str | None = Query(default=None, max_length=16),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(PromptReview)
    if status:
        if status not in {"pending", "approved", "rejected"}:
            raise HTTPException(
                status_code=400, detail="status must be pending, approved or rejected"
            )
        query = query.filter(PromptReview.status == status)
    rows = query.order_by(PromptReview.id.desc()).limit(limit).all()
    return {
        "items": [_prompt_review_item(row) for row in rows],
        "pending": db.query(PromptReview).filter(PromptReview.status == "pending").count(),
        "is_admin": is_admin_user(user),
    }


@router.post("/prompt-reviews", status_code=201)
def submit_prompt_review(
    payload: PromptReviewIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = _load_prompts()
    prompt = next((p for p in data.get("prompts", []) if p.get("id") == payload.prompt_id), None)
    if prompt is None:
        raise HTTPException(status_code=404, detail=f"unknown prompt id: {payload.prompt_id}")
    row = PromptReview(
        prompt_id=payload.prompt_id,
        prompt_version=payload.prompt_version or str(data.get("version") or ""),
        task=payload.task or str(prompt.get("task") or ""),
        comment=payload.comment.strip(),
        proposed_change=payload.proposed_change.strip(),
        submitted_by=user.email,
        submitted_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_event(
        db,
        action="llm.prompt_review_submit",
        actor_user_id=user.id,
        resource_type="prompt_review",
        resource_id=str(row.id),
        detail={"prompt_id": row.prompt_id, "prompt_version": row.prompt_version},
        commit=True,
    )
    return _prompt_review_item(row)


@router.post("/prompt-reviews/{review_id}/review")
def review_prompt_review(
    review_id: int,
    payload: PromptReviewDecision,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.get(PromptReview, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="prompt review not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"prompt review already {row.status}")
    row.status = payload.status
    row.review_note = payload.review_note.strip()
    row.reviewed_by = admin.email
    row.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    log_event(
        db,
        action="llm.prompt_review_decision",
        actor_user_id=admin.id,
        resource_type="prompt_review",
        resource_id=str(row.id),
        status=row.status,
        detail={"prompt_id": row.prompt_id, "note": row.review_note},
        commit=True,
    )
    return _prompt_review_item(row)


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
