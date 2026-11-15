from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..mail_sync import cleanup_retention, get_state, sync_connection
from ..models import (
    Campaign,
    CampaignMessage,
    Contact,
    EmailConnection,
    MailSyncState,
    MarketingCompany,
    MessageTemplate,
    SyncRun,
    User,
)
from ..schemas import (
    EmailConnectionCreate,
    EmailConnectionOut,
    EmailFetchIn,
    EmailFetchOut,
    EmailMessageContextOut,
    EmailSyncIn,
    EmailTestSendIn,
    SendMailIn,
)
from ..security import decrypt_secret, encrypt_secret, get_current_user
from ..services import EmailExtractor, MailSender, compact_text
from ..templating import contact_context, render_resolved

router = APIRouter(prefix="/email", tags=["email"])


def _owned_connection(connection_id: int, user: User, db: Session) -> EmailConnection:
    connection = (
        db.query(EmailConnection)
        .filter(EmailConnection.id == connection_id, EmailConnection.user_id == user.id)
        .first()
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection


def _email_context(message: dict, payload: EmailFetchIn) -> EmailMessageContextOut | None:
    subject = str(message.get("subject", ""))
    sender = str(message.get("from") or message.get("sender") or "")
    body = str(message.get("body", ""))
    snippet = str(message.get("snippet", ""))
    haystack = f"{subject} {sender} {body} {snippet}".lower()
    if payload.query.strip() and payload.query.strip().lower() not in haystack:
        return None
    if payload.sender.strip() and payload.sender.strip().lower() not in sender.lower():
        return None
    if payload.intent and message.get("intent") != payload.intent:
        return None
    context = compact_text(body or str(message.get("snippet", "")), payload.context_chars)
    result = {
        "uid": str(message.get("uid", "")),
        "subject": subject,
        "sender": sender,
        "date": str(message.get("date", "")),
        "intent": str(message.get("intent", "general")),
        "context": context if payload.include_context else "",
    }
    if payload.include_body:
        result["body"] = body[:10_000]
    return EmailMessageContextOut(**result)


def _fetch_filters(payload: EmailFetchIn) -> dict:
    return {
        "query": payload.query,
        "sender": payload.sender,
        "intent": payload.intent,
        "since": payload.since.isoformat() if payload.since else None,
        "until": payload.until.isoformat() if payload.until else None,
        "unread_only": payload.unread_only,
    }


@router.get("/connections", response_model=list[EmailConnectionOut])
def list_connections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(EmailConnection).filter(EmailConnection.user_id == user.id).all()


@router.post("/connections", response_model=EmailConnectionOut, status_code=201)
def add_connection(
    payload: EmailConnectionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = EmailConnection(
        user_id=user.id,
        email_address=payload.email_address,
        imap_host=payload.imap_host,
        imap_port=payload.imap_port,
        smtp_host=payload.smtp_host,
        smtp_port=payload.smtp_port,
        secret_encrypted=encrypt_secret(payload.password),
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.post("/connections/{connection_id}/test")
def test_connection(
    connection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = (
        db.query(EmailConnection)
        .filter(EmailConnection.id == connection_id, EmailConnection.user_id == user.id)
        .first()
    )
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    password = decrypt_secret(conn.secret_encrypted)
    result: dict[str, str] = {}

    extractor = EmailExtractor(conn.imap_host, conn.imap_port, conn.email_address, password)
    try:
        extractor.connect()
        result["imap"] = "connected"
    except Exception as exc:  # noqa: BLE001
        result["imap"] = f"failed: {exc}"
    finally:
        extractor.disconnect()

    sender = MailSender(conn.smtp_host, conn.smtp_port, conn.email_address, password)
    try:
        sender.send(conn.email_address, "Kalisoft connection test", "SMTP OK")
        result["smtp"] = "connected"
    except Exception as exc:  # noqa: BLE001
        result["smtp"] = f"failed: {exc}"

    conn.is_connected = result["imap"] == "connected" and result["smtp"] == "connected"
    conn.last_checked_at = datetime.utcnow()
    db.commit()
    return {"connection_id": conn.id, "is_connected": conn.is_connected, **result}


@router.post(
    "/connections/{connection_id}/fetch",
    response_model=EmailFetchOut,
    response_model_exclude_none=True,
)
def fetch_connection(
    connection_id: int,
    payload: EmailFetchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = _owned_connection(connection_id, user, db)
    extractor = EmailExtractor(
        conn.imap_host, conn.imap_port, conn.email_address, decrypt_secret(conn.secret_encrypted)
    )
    try:
        messages = extractor.fetch_emails(
            limit=payload.limit,
            query=payload.query,
            sender=payload.sender,
            since=payload.since,
            until=payload.until,
            unread_only=payload.unread_only,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"IMAP error: {exc}") from exc
    finally:
        extractor.disconnect()
    context_messages = [
        context for message in messages if (context := _email_context(message, payload)) is not None
    ][: payload.limit]
    return EmailFetchOut(
        connection_id=conn.id,
        count=len(context_messages),
        scanned=len(messages),
        messages=context_messages,
        filters=_fetch_filters(payload),
        options={
            "include_context": payload.include_context,
            "include_body": payload.include_body,
            "context_chars": payload.context_chars,
        },
    )


@router.get(
    "/connections/{connection_id}/inbox",
    response_model=EmailFetchOut,
    response_model_exclude_none=True,
)
def read_inbox(
    connection_id: int,
    limit: int = Query(default=15, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return fetch_connection(connection_id, EmailFetchIn(limit=limit), user, db)


@router.post("/send")
def send_mail(
    payload: SendMailIn,
    connection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = (
        db.query(EmailConnection)
        .filter(EmailConnection.id == connection_id, EmailConnection.user_id == user.id)
        .first()
    )
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    sender = MailSender(
        conn.smtp_host, conn.smtp_port, conn.email_address, decrypt_secret(conn.secret_encrypted)
    )
    try:
        result = sender.send(payload.to, payload.subject, payload.body, conn.email_address)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"SMTP error: {exc}") from exc
    return result


# ---------------------------------------------------------------------------
# Incremental IMAP sync, checkpoints, analytics, test-send, retention
# ---------------------------------------------------------------------------


@router.post("/default-connection", response_model=EmailConnectionOut, status_code=201)
def ensure_default_connection(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create/refresh the workspace mailbox directly from .env credentials.

    Uses IMAP_HOST/PORT/USER + SMTP_HOST/PORT + SMTP_PASSWORD (or Gmail app
    password) already loaded from .env. No Secret Manager. The password is
    encrypted at rest and never returned by any API.
    """
    address = (settings.IMAP_USER or settings.SMTP_USER or settings.GMAIL_ADDRESS).strip()
    password = (settings.SMTP_PASSWORD or settings.GMAIL_APP_PASSWORD).strip()
    if not address or not password:
        raise HTTPException(
            status_code=400, detail="IMAP/SMTP credentials are not configured in .env"
        )
    imap_host = (settings.IMAP_HOST or "imap.gmail.com").strip()
    smtp_host = (settings.SMTP_HOST or "smtp.gmail.com").strip()
    conn = (
        db.query(EmailConnection)
        .filter(EmailConnection.user_id == user.id, EmailConnection.email_address == address)
        .first()
    )
    if conn is None:
        conn = EmailConnection(user_id=user.id, email_address=address)
        db.add(conn)
    conn.imap_host = imap_host
    conn.imap_port = int(settings.IMAP_PORT or 993)
    conn.smtp_host = smtp_host
    conn.smtp_port = int(settings.SMTP_PORT or 587)
    conn.secret_encrypted = encrypt_secret(password)
    db.commit()
    db.refresh(conn)
    return conn


@router.post("/connections/{connection_id}/sync")
def sync_mailbox(
    connection_id: int,
    payload: EmailSyncIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Incremental read-only sync (UID checkpoint + Message-ID dedup).

    Default fetch = only mail newer than the checkpoint (first run = today).
    Raw EML, attachments and processed JSON are written to GCS
    gs://kalika_enterprises/Kalika_gmail_data/. Original mailbox is untouched.
    """
    conn = _owned_connection(connection_id, user, db)
    result = sync_connection(
        db,
        conn,
        user,
        batch=payload.batch,
        full=payload.full,
        query=payload.query,
        sender=payload.sender,
        since=payload.since,
        until=payload.until,
        unread_only=payload.unread_only,
        before_uid=payload.before_uid,
    )
    if result.get("status") == "error":
        state = get_state(db, conn.id, user.id)
        raise HTTPException(status_code=502, detail=state.last_error or "IMAP sync failed")
    return result


@router.get("/connections/{connection_id}/sync/state")
def sync_state(
    connection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = _owned_connection(connection_id, user, db)
    state = get_state(db, conn.id, user.id)
    runs = (
        db.query(SyncRun)
        .filter(SyncRun.job.in_(("email_sync", "mail_retention")))
        .order_by(SyncRun.id.desc())
        .limit(10)
        .all()
    )
    daily = (state.stats or {}).get("daily") or {}
    return {
        "connection_id": conn.id,
        "mailbox": state.mailbox,
        "uidvalidity": state.uidvalidity,
        "last_uid": state.last_uid,
        "dedup_ids": len(state.message_ids or []),
        "last_sync_at": str(state.last_sync_at or ""),
        "last_status": state.last_status,
        "last_error": state.last_error,
        "gcs_last_prefix": state.gcs_last_prefix,
        "daily": dict(sorted(daily.items())[-30:]),
        "totals": {
            "fetched": sum(v.get("fetched", 0) for v in daily.values()),
            "processed": sum(v.get("processed", 0) for v in daily.values()),
            "duplicates_skipped": sum(v.get("duplicates_skipped", 0) for v in daily.values()),
        },
        "recent_runs": [
            {
                "id": r.id,
                "job": r.job,
                "status": r.status,
                "detail": r.detail[:300],
                "started_at": str(r.started_at),
            }
            for r in runs
        ],
    }


@router.get("/sync/analytics")
def sync_analytics(
    days: int = Query(default=14, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real dashboard data: mail activity, outreach counts, connection health.

    Nothing is fabricated - mail KPIs come from sync checkpoints, outreach from
    campaign/message rows, health from connection + sync-run records.
    """
    connections = db.query(EmailConnection).filter(EmailConnection.user_id == user.id).all()
    conn_ids = [c.id for c in connections]
    states = (
        db.query(MailSyncState).filter(MailSyncState.connection_id.in_(conn_ids)).all()
        if conn_ids
        else []
    )
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days - 1)).isoformat()
    daily: dict[str, dict[str, int]] = {}
    for st in states:
        for day, counters in ((st.stats or {}).get("daily") or {}).items():
            if day < cutoff:
                continue
            row = daily.setdefault(day, {"fetched": 0, "processed": 0, "duplicates_skipped": 0})
            row["fetched"] += int(counters.get("fetched", 0))
            row["processed"] += int(counters.get("processed", 0))
            row["duplicates_skipped"] += int(counters.get("duplicates_skipped", 0))

    # outreach: real message states across email + WhatsApp/WeChat (last N days)
    since_day = datetime.now(timezone.utc).date() - timedelta(days=days - 1)
    since_dt = datetime.combine(since_day, datetime.min.time())

    def _msg_count(statuses: tuple[str, ...], *, created: bool = False) -> int:
        column = CampaignMessage.created_at if created else CampaignMessage.sent_at
        q = (
            db.query(func.count(CampaignMessage.id))
            .join(Campaign, Campaign.id == CampaignMessage.campaign_id)
            .filter(CampaignMessage.user_id == user.id, column.isnot(None), column >= since_dt)
        )
        if statuses:
            q = q.filter(CampaignMessage.status.in_(statuses))
        return int(q.scalar() or 0)

    sent = _msg_count(("sent", "opened"))
    delivered = _msg_count(("opened",))  # confirmed via tracking pixel
    failed = _msg_count(("failed",))
    pending = _msg_count(("pending_review", "approved", "queued"), created=True)

    channel_rows = (
        db.query(
            Campaign.channel,
            func.coalesce(func.sum(Campaign.sent_count), 0),
            func.coalesce(func.sum(Campaign.failed_count), 0),
            func.coalesce(func.sum(Campaign.total), 0),
        )
        .filter(Campaign.user_id == user.id, Campaign.created_at >= since_dt)
        .group_by(Campaign.channel)
        .all()
    )
    by_channel = [
        {
            "channel": ch or "email",
            "sent": int(s or 0),
            "failed": int(f or 0),
            "pending": max(0, int(t or 0) - int(s or 0) - int(f or 0)),
        }
        for ch, s, f, t in channel_rows
    ]

    # daily sent (by real sent_at dates, all channels)
    day_expr = func.date(CampaignMessage.sent_at)
    sent_rows = (
        db.query(day_expr, CampaignMessage.status, func.count(CampaignMessage.id))
        .join(Campaign, Campaign.id == CampaignMessage.campaign_id)
        .filter(CampaignMessage.user_id == user.id, CampaignMessage.sent_at.isnot(None))
        .group_by(day_expr, CampaignMessage.status)
        .all()
    )
    sent_daily: dict[str, dict[str, int]] = {}
    for day, status, count in sent_rows:
        try:
            d = (
                day
                if isinstance(day, str)
                else day.strftime("%Y-%m-%d")
                if hasattr(day, "strftime")
                else str(day)
            )
        except Exception:  # noqa: BLE001
            continue
        if d < since_day.isoformat():
            continue
        row = sent_daily.setdefault(d, {"sent": 0, "failed": 0, "opened": 0})
        if status in ("sent", "opened"):
            row["sent"] += int(count)
        elif status == "failed":
            row["failed"] += int(count)
        if status == "opened":
            row["opened"] += int(count)

    last_run = (
        db.query(SyncRun)
        .filter(SyncRun.job.in_(("email_sync", "mail_retention")))
        .order_by(SyncRun.id.desc())
        .first()
    )
    return {
        "days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mail": {
            "fetched": sum(v["fetched"] for v in daily.values()),
            "processed": sum(v["processed"] for v in daily.values()),
            "duplicates_skipped": sum(v.get("duplicates_skipped", 0) for v in daily.values()),
            "daily": [
                {"day": k, **v, **{sk: sv for sk, sv in sent_daily.get(k, {}).items()}}
                for k, v in sorted(daily.items())
            ],
            "last_sync_at": str(
                max((st.last_sync_at for st in states if st.last_sync_at), default="") or ""
            ),
        },
        "outreach": {
            "sent": sent,
            "delivered": delivered,
            "failed": failed,
            "pending": pending,
            "by_channel": by_channel,
            "daily_sent": [{"day": k, **v} for k, v in sorted(sent_daily.items())],
        },
        "connections": [
            {
                "id": c.id,
                "email_address": c.email_address,
                "imap_host": c.imap_host,
                "is_connected": c.is_connected,
                "last_checked_at": str(c.last_checked_at or ""),
            }
            for c in connections
        ],
        "sync_health": {
            "last_job": last_run.job if last_run else "",
            "last_status": last_run.status if last_run else "never",
            "last_at": str(last_run.started_at) if last_run else "",
            "last_detail": (last_run.detail[:300] if last_run else ""),
            "gcs_prefix": settings.GCS_PATH_GMAIL,
            "retention_days": {
                "raw": settings.MAIL_RETENTION_RAW_DAYS,
                "processed": settings.MAIL_RETENTION_PROCESSED_DAYS,
                "attachments": settings.MAIL_RETENTION_ATTACHMENTS_DAYS,
                "logs": settings.MAIL_RETENTION_LOGS_DAYS,
            },
        },
    }


@router.post("/retention/cleanup")
def retention_cleanup(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Enforce GCS retention windows (raw 180d, processed 365d, attachments 90d,
    logs 365d). Deletes only our exported objects - never mailbox emails."""
    return cleanup_retention(db)


@router.post("/connections/{connection_id}/test-send")
def test_send(
    connection_id: int,
    payload: EmailTestSendIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Personalize a template for one contact and send a real test to yourself.

    Subject/body run through the same render_resolved pipeline as campaigns, so
    what you preview is exactly what would be sent. No unresolved placeholders.
    """
    conn = _owned_connection(connection_id, user, db)
    subject = payload.subject
    body = payload.body
    rendered_for = ""
    if payload.template_id:
        template = (
            db.query(MessageTemplate)
            .filter(MessageTemplate.id == payload.template_id, MessageTemplate.user_id == user.id)
            .first()
        )
        if template is None:
            raise HTTPException(status_code=404, detail="Template not found")
        subject = subject or template.subject or ""
        body = body or template.body or ""
        if payload.contact_id:
            if payload.contact_type == "marketing_companies":
                record = (
                    db.query(MarketingCompany)
                    .filter(
                        MarketingCompany.id == payload.contact_id,
                        MarketingCompany.user_id == user.id,
                    )
                    .first()
                )
                if record is None:
                    raise HTTPException(status_code=404, detail="Contact not found")
                contact = record
                rendered_for = record.company
            else:
                contact = (
                    db.query(Contact)
                    .filter(Contact.id == payload.contact_id, Contact.user_id == user.id)
                    .first()
                )
                if contact is None:
                    raise HTTPException(status_code=404, detail="Contact not found")
                rendered_for = contact.company or contact.name
        ctx = {**contact_context(contact)} if payload.contact_id else {}
        ctx.setdefault("product_name", "Kalika Enterprises packaging")
        subject = render_resolved(subject, ctx)
        body = render_resolved(body, ctx)
    if "{{" in subject or "{{" in body:
        raise HTTPException(
            status_code=400, detail="Unresolved personalization placeholder - fix the template"
        )
    to = payload.to.strip() or conn.email_address
    sender = MailSender(
        conn.smtp_host, conn.smtp_port, conn.email_address, decrypt_secret(conn.secret_encrypted)
    )
    try:
        result = sender.send(
            to, subject or "Kalika test send", body, conn.email_address, html=payload.html
        )
    except Exception as exc:  # noqa: BLE001
        db.add(
            SyncRun(
                job="email_sync",
                status="error",
                detail=f"test-send to {to}: {exc}"[:1000],
                finished_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        raise HTTPException(status_code=502, detail=f"SMTP test-send failed: {exc}") from exc
    db.add(
        SyncRun(
            job="email_sync",
            status="ok",
            detail=f"test-send to {to}: OK",
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return {
        "ok": True,
        "to": to,
        "subject": subject,
        "rendered_for": rendered_for,
        "preview_body": body[:2000],
        **result,
    }
