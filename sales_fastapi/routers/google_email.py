from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..gmail_sync import message_out, sync_gmail_mailbox
from ..governance.audit import log_event
from ..models import GmailMessage, GmailSyncState, GoogleMailbox, User
from ..schemas import EmailFetchIn, EmailFetchOut, GoogleMailboxOut, GoogleOAuthAuthorizeOut
from ..security import (
    create_oauth_state,
    decode_oauth_state,
    decrypt_secret,
    encrypt_secret,
    get_current_user,
)
from ..services import GCSStorage, GmailExtractor, GoogleOAuthClient
from .email import _email_context, _fetch_filters

router = APIRouter(prefix="/email/google", tags=["email"])


def _mailbox_redirect(status: str) -> RedirectResponse:
    base = settings.FRONTEND_URL.rstrip("/")
    separator = "&" if "?" in base else "?"
    return RedirectResponse(f"{base}/?{separator}gmail={status}", status_code=303)


@router.get("/mailboxes", response_model=list[GoogleMailboxOut])
def list_mailboxes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(GoogleMailbox)
        .filter(GoogleMailbox.user_id == user.id)
        .order_by(GoogleMailbox.created_at.desc())
        .all()
    )


@router.get("/authorize", response_model=GoogleOAuthAuthorizeOut)
def authorize(user: User = Depends(get_current_user)):
    if not settings.google_gmail_oauth_configured:
        raise HTTPException(status_code=503, detail="Google Gmail OAuth is not configured")
    state = create_oauth_state(user.id, "gmail_connect")
    return GoogleOAuthAuthorizeOut(
        authorization_url=GoogleOAuthClient().authorization_url(state),
        expires_in=600,
    )


@router.get("/callback")
def callback(
    code: str = Query(default="", max_length=2048),
    state: str = Query(default="", max_length=4096),
    error: str = Query(default="", max_length=256),
    db: Session = Depends(get_db),
):
    if error:
        return _mailbox_redirect("error")
    if not code or not state:
        return _mailbox_redirect("error")
    try:
        user_id = decode_oauth_state(state, "gmail_connect")
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return _mailbox_redirect("error")
        token_data = GoogleOAuthClient().exchange_code(code)
        access_token = str(token_data.get("access_token", ""))
        if not access_token:
            return _mailbox_redirect("error")
        profile = GmailExtractor(access_token).profile()
        email_address = str(profile.get("emailAddress", "")).strip().lower()
        if not email_address:
            return _mailbox_redirect("error")
        mailbox = (
            db.query(GoogleMailbox)
            .filter(
                GoogleMailbox.user_id == user.id,
                GoogleMailbox.email_address == email_address,
            )
            .first()
        )
        if mailbox is None:
            mailbox = GoogleMailbox(user_id=user.id, email_address=email_address)
            db.add(mailbox)
        mailbox.access_token_encrypted = encrypt_secret(access_token)
        refresh_token = str(token_data.get("refresh_token", ""))
        if refresh_token:
            mailbox.refresh_token_encrypted = encrypt_secret(refresh_token)
        mailbox.token_expiry = datetime.utcnow() + timedelta(
            seconds=max(60, int(token_data.get("expires_in", 3600)))
        )
        mailbox.scopes = str(token_data.get("scope", GoogleOAuthClient.gmail_scope))
        mailbox.is_connected = True
        mailbox.last_checked_at = datetime.utcnow()
        db.commit()
        log_event(
            db,
            action="email.google_connected",
            actor_user_id=user.id,
            resource_type="google_mailbox",
            resource_id=str(mailbox.id),
            tenant_id=user.domain,
            detail={"provider": "google", "email": email_address},
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        return _mailbox_redirect("error")
    return _mailbox_redirect("connected")


@router.post(
    "/mailboxes/{mailbox_id}/fetch",
    response_model=EmailFetchOut,
    response_model_exclude_none=True,
)
def fetch_mailbox(
    mailbox_id: int,
    payload: EmailFetchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mailbox = (
        db.query(GoogleMailbox)
        .filter(GoogleMailbox.id == mailbox_id, GoogleMailbox.user_id == user.id)
        .first()
    )
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Google mailbox not found")
    access_token = decrypt_secret(mailbox.access_token_encrypted)
    if not access_token:
        raise HTTPException(status_code=400, detail="Google mailbox is not authorized")
    if mailbox.token_expiry and mailbox.token_expiry <= datetime.utcnow() + timedelta(seconds=60):
        refresh_token = decrypt_secret(mailbox.refresh_token_encrypted)
        try:
            token_data = GoogleOAuthClient().refresh_access_token(refresh_token)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=502, detail="Google OAuth token refresh failed"
            ) from exc
        access_token = str(token_data.get("access_token", ""))
        if not access_token:
            raise HTTPException(status_code=502, detail="Google OAuth token refresh failed")
        mailbox.access_token_encrypted = encrypt_secret(access_token)
        mailbox.token_expiry = datetime.utcnow() + timedelta(
            seconds=max(60, int(token_data.get("expires_in", 3600)))
        )
        db.commit()
    try:
        scanned, messages = GmailExtractor(access_token).fetch_emails(
            limit=payload.limit,
            query=payload.query,
            sender=payload.sender,
            since=payload.since,
            until=payload.until,
            unread_only=payload.unread_only,
            include_body=payload.include_body,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="Gmail API error") from exc
    context_messages = [
        context for message in messages if (context := _email_context(message, payload)) is not None
    ][: payload.limit]
    mailbox.last_checked_at = datetime.utcnow()
    db.commit()
    return EmailFetchOut(
        connection_id=mailbox.id,
        source="gmail",
        count=len(context_messages),
        scanned=scanned,
        messages=context_messages,
        filters=_fetch_filters(payload),
        options={
            "include_context": payload.include_context,
            "include_body": payload.include_body,
            "context_chars": payload.context_chars,
        },
    )


def _owned_mailbox(mailbox_id: int, user: User, db: Session) -> GoogleMailbox:
    mailbox = (
        db.query(GoogleMailbox)
        .filter(GoogleMailbox.id == mailbox_id, GoogleMailbox.user_id == user.id)
        .first()
    )
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Google mailbox not found")
    return mailbox


def _attachment_url(path: str) -> str:
    if not path:
        return ""
    gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_MAIL)
    if gcs.available and gcs._client is not None:
        try:
            blob = gcs._client.bucket(gcs.bucket_name).blob(path)
            return blob.generate_signed_url(
                expires=datetime.utcnow() + timedelta(hours=1), method="GET"
            )
        except Exception:  # noqa: BLE001 - graceful fallback
            pass
    return f"https://storage.googleapis.com/{gcs.bucket_name}/{path}"


@router.post("/mailboxes/{mailbox_id}/sync")
def sync_mailbox_drilldown(
    mailbox_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Incremental Gmail history sync (backend-only, checkpointed + deduped)."""
    mailbox = _owned_mailbox(mailbox_id, user, db)
    try:
        result = sync_gmail_mailbox(db, mailbox, user)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    log_event(
        db,
        action="email.google_incremental_sync",
        actor_user_id=user.id,
        resource_type="google_mailbox",
        resource_id=str(mailbox.id),
        tenant_id=user.domain,
        detail={
            "scanned": result["scanned"],
            "created": result["created"],
            "updated": result["updated"],
        },
        commit=True,
    )
    return result


@router.get("/mailboxes/{mailbox_id}/sync-state")
def mailbox_sync_state(
    mailbox_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned_mailbox(mailbox_id, user, db)
    state = db.query(GmailSyncState).filter(GmailSyncState.mailbox_id == mailbox_id).first()
    if state is None:
        return {"mailbox_id": mailbox_id, "status": "never", "messages_stored": 0}
    stored = (
        db.query(func.count(GmailMessage.id))
        .filter(GmailMessage.mailbox_id == mailbox_id)
        .scalar()
        or 0
    )
    return {
        "mailbox_id": mailbox_id,
        "status": state.last_status or "never",
        "history_id": state.history_id,
        "messages_stored": stored,
        "stats": state.stats or {},
        "last_error": state.last_error,
        "last_sync_at": str(state.last_sync_at) if state.last_sync_at else None,
    }


@router.get("/mailboxes/{mailbox_id}/messages")
def list_mailbox_messages(
    mailbox_id: int,
    q: str = Query(default="", max_length=256),
    intent: str = Query(default="", max_length=64),
    client: str = Query(default="", max_length=255),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Second-level mail list for conversation drilldown."""
    _owned_mailbox(mailbox_id, user, db)
    query = db.query(GmailMessage).filter(GmailMessage.mailbox_id == mailbox_id)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                GmailMessage.subject.ilike(pattern),
                GmailMessage.sender.ilike(pattern),
                GmailMessage.sender_email.ilike(pattern),
                GmailMessage.snippet.ilike(pattern),
                GmailMessage.client.ilike(pattern),
            )
        )
    if intent:
        query = query.filter(GmailMessage.intent == intent.strip().lower())
    if client:
        query = query.filter(GmailMessage.client.ilike(f"%{client.strip()}%"))
    total = query.count()
    rows = query.order_by(GmailMessage.internal_date.desc(), GmailMessage.id.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "messages": [message_out(row, include_body=False) for row in rows],
    }


@router.get("/mailboxes/{mailbox_id}/messages/{message_id}")
def get_mailbox_message(
    mailbox_id: int,
    message_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned_mailbox(mailbox_id, user, db)
    row = (
        db.query(GmailMessage)
        .filter(GmailMessage.mailbox_id == mailbox_id, GmailMessage.message_id == message_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Gmail message not found")
    payload: dict[str, Any] = message_out(row, include_body=True)
    for item in payload["attachments"]:
        item["url"] = _attachment_url(str(item.get("gcs_path", "")))
    return payload


@router.get("/mailboxes/{mailbox_id}/threads/{thread_id}")
def get_mailbox_thread(
    mailbox_id: int,
    thread_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned_mailbox(mailbox_id, user, db)
    rows = (
        db.query(GmailMessage)
        .filter(GmailMessage.mailbox_id == mailbox_id, GmailMessage.thread_id == thread_id)
        .order_by(GmailMessage.internal_date.asc(), GmailMessage.id.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Gmail thread not found")
    return {
        "thread_id": thread_id,
        "message_count": len(rows),
        "subject": rows[0].subject,
        "client": rows[0].client,
        "messages": [message_out(row, include_body=True) for row in rows],
    }
