"""Instore mail desk: mailbox sync, insights, missing links, and expert chat."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..instore_mail import (
    build_insights,
    load_dump_mails,
    load_insights,
    save_insights,
)
from ..llm.guardrails import scan_prompt, validate_output
from ..llm.providers import log_llm_error, tag_llm_error
from ..llm.router import estimate_cost_micros
from ..models import Contact, EmailConnection, GoogleMailbox, ModelUsage, SyncRun, User
from ..security import decrypt_secret, encrypt_secret, get_current_user
from ..services import EmailExtractor, GmailExtractor, GoogleOAuthClient
from .ops import _chat_chain, _model_available, _provider_for

router = APIRouter(prefix="/instore", tags=["instore"])

EXPERTISE = [
    {
        "id": "sales_strategist",
        "label": "Sales strategist",
        "description": "Prioritise accounts, next best action, pipeline risk.",
        "system": "Act as a senior B2B packaging sales strategist. Be concise and commercial.",
    },
    {
        "id": "key_account_manager",
        "label": "Key account manager",
        "description": "Relationship history, follow-ups, escalation language.",
        "system": "Act as a key account manager. Focus on relationship continuity and commitments.",
    },
    {
        "id": "technical_advisor",
        "label": "Technical advisor",
        "description": "Film specs, microns, width, density, application fit.",
        "system": "Act as a flexible-packaging technical advisor. Explain specs and trade-offs.",
    },
    {
        "id": "finance_pricing",
        "label": "Finance & pricing",
        "description": "Quotes, margins, payment terms, cost risk.",
        "system": "Act as a pricing and finance reviewer. Quantify margin and payment risk.",
    },
    {
        "id": "field_executive",
        "label": "Field executive",
        "description": "Visit notes, location, previous discussion, mail trail.",
        "system": "Act as a field sales executive preparing for an in-person client meeting.",
    },
]


class SyncIn(BaseModel):
    mailbox_id: int = 0
    source: Literal["auto", "gmail", "imap", "dump"] = "auto"
    limit: int = Field(default=50, ge=1, le=200)
    query: str = Field(default="", max_length=256)
    include_body: bool = True
    include_dump: bool = True


class AskIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=4000)
    expertise: str = Field(default="sales_strategist", max_length=64)
    model: str = Field(default="", max_length=128)
    mail_limit: int = Field(default=8, ge=1, le=50)


def _contacts(db: Session, user: User) -> list[dict]:
    rows = db.query(Contact).filter(Contact.user_id == user.id).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "email": row.email,
            "phone": row.phone,
            "domain": row.domain,
            "company": row.company,
        }
        for row in rows
    ]


def _mailbox_access(db: Session, user: User, mailbox_id: int) -> tuple[GoogleMailbox, str]:
    query = db.query(GoogleMailbox).filter(
        GoogleMailbox.user_id == user.id, GoogleMailbox.is_connected.is_(True)
    )
    if mailbox_id:
        query = db.query(GoogleMailbox).filter(
            GoogleMailbox.user_id == user.id, GoogleMailbox.id == mailbox_id
        )
    mailbox = query.order_by(GoogleMailbox.created_at.desc()).first()
    if mailbox is None:
        raise HTTPException(status_code=400, detail="Connect a Google mailbox first")
    token = decrypt_secret(mailbox.access_token_encrypted)
    if not token:
        raise HTTPException(status_code=400, detail="Google mailbox is not authorized")
    if mailbox.token_expiry and mailbox.token_expiry <= datetime.utcnow() + timedelta(seconds=60):
        refresh = decrypt_secret(mailbox.refresh_token_encrypted)
        try:
            token_data = GoogleOAuthClient().refresh_access_token(refresh)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=502, detail="Google OAuth token refresh failed"
            ) from exc
        token = str(token_data.get("access_token", ""))
        if not token:
            raise HTTPException(status_code=502, detail="Google OAuth token refresh failed")
        mailbox.access_token_encrypted = encrypt_secret(token)
        mailbox.token_expiry = datetime.utcnow() + timedelta(
            seconds=max(60, int(token_data.get("expires_in", 3600)))
        )
        db.commit()
    return mailbox, token


def _imap_access(db: Session, user: User) -> EmailConnection:
    connection = (
        db.query(EmailConnection)
        .filter(EmailConnection.user_id == user.id)
        .order_by(EmailConnection.created_at.desc())
        .first()
    )
    if connection is None:
        raise HTTPException(status_code=400, detail="Connect an IMAP mailbox first")
    return connection


def _collect(payload: SyncIn, db: Session, user: User) -> tuple[list[dict], dict]:
    limit = min(payload.limit, settings.INSTORE_MAIL_SYNC_LIMIT)
    source: dict = {"kind": "dump" if payload.source == "dump" else payload.source, "mails": []}
    mails: list[dict] = []
    errors: list[str] = []

    if payload.source in {"auto", "gmail"}:
        try:
            mailbox, token = _mailbox_access(db, user, payload.mailbox_id)
            scanned, rows = GmailExtractor(token).fetch_emails(
                limit=limit,
                query=payload.query,
                include_body=payload.include_body,
            )
            mails.extend(dict(row, source="gmail") for row in rows)
            source = {"kind": "gmail", "mailbox": mailbox.email_address, "scanned": scanned}
        except HTTPException as exc:
            if payload.source == "gmail":
                raise
            errors.append(str(exc.detail))
        except Exception as exc:  # noqa: BLE001 - report, then fall back to dump
            if payload.source == "gmail":
                raise HTTPException(status_code=502, detail=f"Gmail fetch failed: {exc}") from exc
            errors.append(f"Gmail fetch failed: {exc}")

    if payload.source in {"auto", "imap"} and not mails:
        try:
            connection = _imap_access(db, user)
            extractor = EmailExtractor(
                connection.imap_host,
                connection.imap_port,
                connection.email_address,
                decrypt_secret(connection.secret_encrypted),
            )
            try:
                rows = extractor.fetch_emails(limit=limit, query=payload.query)
            finally:
                extractor.disconnect()
            mails.extend(dict(row, source="imap") for row in rows)
            source = {"kind": "imap", "mailbox": connection.email_address, "scanned": len(rows)}
        except HTTPException as exc:
            if payload.source == "imap":
                raise
            errors.append(str(exc.detail))
        except Exception as exc:  # noqa: BLE001 - report, then fall back to dump
            if payload.source == "imap":
                raise HTTPException(status_code=502, detail=f"IMAP fetch failed: {exc}") from exc
            errors.append(f"IMAP fetch failed: {exc}")

    if payload.include_dump or (payload.source == "dump") or not mails:
        dump = load_dump_mails()
        mails.extend(dict(row, source="dump") for row in dump)
        source = {**source, "dump_mails": len(dump)}

    source["errors"] = errors
    return mails, source


@router.get("/summary")
def summary(user: User = Depends(get_current_user)):
    payload = load_insights()
    return {
        "data_available": bool(payload.get("data_available")),
        "generated_at": payload.get("generated_at"),
        "source": payload.get("source", {}),
        "insights": payload.get("insights", {}),
        "missing_links": payload.get("missing_links", {}),
        "graph_stats": (payload.get("graph") or {}).get("stats", {}),
        "mailbox_scope": str(user.id),
    }


@router.get("/mails")
def list_mails(
    limit: int = Query(default=25, ge=1, le=200),
    intent: str = "",
    only_missing: bool = False,
    user: User = Depends(get_current_user),
):
    payload = load_insights()
    rows = list(payload.get("mails", []))
    if intent:
        rows = [row for row in rows if row.get("intent") == intent]
    if only_missing:
        rows = [row for row in rows if not row.get("contact_id")]
    return {
        "total": len(rows),
        "mails": rows[:limit],
        "generated_at": payload.get("generated_at"),
    }


@router.get("/graph")
def graph(user: User = Depends(get_current_user)):
    payload = load_insights()
    return payload.get("graph") or {"nodes": [], "edges": [], "stats": {}}


@router.post("/sync")
def sync(
    payload: SyncIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started = datetime.utcnow()
    mails, source = _collect(payload, db, user)
    if not mails:
        raise HTTPException(
            status_code=400,
            detail=(
                "No mails available. Connect a Google/IMAP mailbox or add "
                "gcs_data/interaction_dump.json, then retry."
            ),
        )
    insights = build_insights(mails, _contacts(db, user), source=source)
    stored = save_insights(insights)
    run = SyncRun(
        job="instore_mail_sync",
        status="ok",
        detail=(
            f"{insights['insights']['total']} mails, "
            f"{insights['insights']['linked']} linked, "
            f"{insights['missing_links']['count']} missing, "
            f"gcs={stored['gcs_uploaded']}, source={source.get('kind')}"
        ),
        finished_at=datetime.utcnow(),
    )
    db.add(run)
    log_event(
        db,
        action="instore.mail_sync",
        actor_user_id=user.id,
        resource_type="instore_mails",
        resource_id=str(insights["insights"]["total"]),
        status="ok",
        detail={
            "source": source,
            "elapsed_ms": int((datetime.utcnow() - started).total_seconds() * 1000),
        },
        commit=False,
    )
    db.commit()
    return {
        "ok": True,
        "stored": stored,
        "sync_run_id": run.id,
        "source": source,
        "insights": insights["insights"],
        "missing_links": insights["missing_links"],
        "graph_stats": insights["graph"]["stats"],
    }


def _snapshot_context(payload: dict, limit: int = 8) -> str:
    insights = payload.get("insights", {})
    lines = [
        f"Total mails: {insights.get('total', 0)}; linked contacts: {insights.get('linked', 0)}; "
        f"unlinked: {insights.get('unlinked', 0)}",
        f"Intents: {insights.get('by_intent', {})}",
        f"Attachments: {insights.get('attachments', 0)}; purposes: {insights.get('attachment_purposes', {})}",
        f"Missing links: {(payload.get('missing_links') or {}).get('count', 0)}",
        "Latest mails:",
    ]
    for mail in (payload.get("mails") or [])[:limit]:
        title = mail.get("working_title") or mail.get("subject", "")
        client = mail.get("client_name") or mail.get("company") or "unknown"
        lines.append(
            f"- [{str(mail.get('date', ''))[:10]}] {client} | {title[:90]} "
            f"| intent={mail.get('intent', '')} | outcome={mail.get('outcome', '')}"
        )
    samples = (payload.get("missing_links") or {}).get("samples", [])[:8]
    if samples:
        lines.append("Missing contact links:")
        for item in samples:
            lines.append(
                f"- {item.get('from_email')} ({item.get('domain')}) subject={item.get('subject')}"
            )
    return "\n".join(lines)


def _dynamic_prompt(question: str, payload: dict, expertise: dict, mail_limit: int) -> str:
    return (
        f"Role: {expertise['system']}\n"
        "Use only the snapshot below. Cite sender/subject when recommending an action. "
        "Return: (1) summary, (2) priority accounts, (3) missing links to fix, "
        "(4) next actions with owner and timing.\n\n"
        f"INSTORE MAIL SNAPSHOT\n{_snapshot_context(payload, mail_limit)}\n\n"
        f"QUESTION\n{question}"
    )


@router.get("/prompts")
def prompts(user: User = Depends(get_current_user)):
    payload = load_insights()
    return {
        "models": {
            "default": settings.LLM_GEMMA_MODEL,
            "gemma": settings.LLM_GEMMA_MODEL,
            "flash": settings.LLM_CLOUD_FLASH_MODEL,
            "local": settings.LLM_CHAT_LOCAL_MODEL,
        },
        "expertise": EXPERTISE,
        "prompt_preview": _dynamic_prompt(
            "What should the field team do next?", payload, EXPERTISE[0], 8
        ),
        "snapshot": {
            "data_available": payload.get("data_available"),
            "mails": (payload.get("insights") or {}).get("total", 0),
        },
    }


@router.post("/ask")
def ask(
    payload: AskIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expertise = next((item for item in EXPERTISE if item["id"] == payload.expertise), EXPERTISE[0])
    snapshot = load_insights()
    prompt = _dynamic_prompt(payload.question, snapshot, expertise, payload.mail_limit)
    report = scan_prompt(prompt, max_chars=settings.LLM_MAX_INPUT_CHARS, redact_pii=True)
    if not report.allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Prompt blocked by guardrails: {', '.join(report.reasons)}",
        )
    attempts: list[dict] = []
    fallback_used = False
    for model_id in _chat_chain(payload.model or settings.LLM_GEMMA_MODEL):
        provider = _provider_for(model_id)
        if provider is None or not provider.available or not _model_available(provider.name):
            attempts.append({"model": model_id, "status": "unavailable", "tag": "llm:unavailable"})
            fallback_used = True
            continue
        try:
            result = provider.generate(
                prompt=report.sanitized,
                system=expertise["system"],
                model=model_id,
                max_output_tokens=512,
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001 - fall through to the next model
            tag = tag_llm_error(exc)
            log_llm_error(tag, model=model_id, task="instore_mail_chat", detail=str(exc))
            attempts.append(
                {"model": model_id, "status": f"error:{type(exc).__name__}", "tag": tag}
            )
            fallback_used = True
            continue
        output = validate_output(result.text, max_chars=settings.LLM_MAX_OUTPUT_CHARS)
        if not output.allowed:
            attempts.append({"model": model_id, "status": "invalid_output"})
            fallback_used = True
            continue
        cost = estimate_cost_micros(result.model, result.input_tokens, result.output_tokens)
        db.add(
            ModelUsage(
                user_id=user.id,
                task="instore_mail_chat",
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
            action="instore.mail_chat",
            actor_user_id=user.id,
            resource_type="instore_mails",
            resource_id=expertise["id"],
            status="ok",
            detail={"model": result.model, "requested": payload.model or settings.LLM_GEMMA_MODEL},
            commit=False,
        )
        db.commit()
        return {
            "reply": result.text,
            "provider": result.provider,
            "model": result.model,
            "expertise": expertise["id"],
            "fallback_used": fallback_used,
            "attempts": attempts,
            "error_tags": [a["tag"] for a in attempts if a.get("tag")],
            "cost_micros": cost,
            "context_mails": (snapshot.get("insights") or {}).get("total", 0),
            "missing_links": (snapshot.get("missing_links") or {}).get("count", 0),
            "notice": "Offline echo model — configure Ollama/Gemini for live answers."
            if result.provider == "echo"
            else "",
        }
    raise HTTPException(status_code=503, detail=f"No model could answer. Attempts: {attempts}")
