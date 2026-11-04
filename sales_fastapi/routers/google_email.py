from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..models import GoogleMailbox, User
from ..schemas import EmailFetchIn, EmailFetchOut, GoogleMailboxOut, GoogleOAuthAuthorizeOut
from ..security import (
    create_oauth_state,
    decode_oauth_state,
    decrypt_secret,
    encrypt_secret,
    get_current_user,
)
from ..services import GmailExtractor, GoogleOAuthClient
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
