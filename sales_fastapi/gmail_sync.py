"""Incremental Gmail history sync + drilldown helpers.

Backs the backend-only Kalika mailbox feature: checkpointed Gmail history,
attachment details in private GCS, and normalized message rows for
conversation/thread drilldown. No UI code is involved.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from .config import settings
from .instore_mail import _CLIENT_DIRECTORY, _attachment_purpose
from .models import GmailMessage, GmailSyncState, GoogleMailbox, User
from .security import decrypt_secret, encrypt_secret
from .services import GCSStorage, GmailExtractor, GoogleOAuthClient, infer_intent

_MAX_DEDUP_IDS = 2000


def _safe_name(value: str, limit: int = 120) -> str:
    cleaned = "".join(c if c.isalnum() or c in "._-" else "_" for c in (value or "").strip())
    return cleaned[:limit] or "item"


def _header(headers: list[dict[str, Any]], name: str) -> str:
    wanted = name.lower()
    for item in headers:
        if str(item.get("name", "")).lower() == wanted:
            return str(item.get("value", "") or "")
    return ""


def _sender_email(value: str) -> str:
    match = re.search(r"<([^>]+)>", value or "")
    return (match.group(1) if match else value).strip().lower()


def _client_for(sender_email: str, text: str) -> str:
    direct = _CLIENT_DIRECTORY.get(sender_email)
    if direct:
        return direct["client"]
    lowered = text.lower()
    for _, info in _CLIENT_DIRECTORY.items():
        client = info["client"].split("(")[0].strip().lower()
        if client and client in lowered:
            return info["client"]
    for keyword, label in (
        ("jsw", "JSW"),
        ("instor", "Instor India"),
        ("jabil", "Jabil"),
        ("cummins", "Cummins DG"),
    ):
        if keyword in lowered:
            return label
    return ""


def gmail_access_token(db: Session, mailbox: GoogleMailbox) -> str:
    """Return a usable access token, refreshing and re-encrypting when needed."""
    token = decrypt_secret(mailbox.access_token_encrypted)
    now = datetime.utcnow()
    if token and not (mailbox.token_expiry and mailbox.token_expiry <= now + timedelta(seconds=60)):
        return token
    refresh_token = decrypt_secret(mailbox.refresh_token_encrypted)
    if not refresh_token:
        return token
    data = GoogleOAuthClient().refresh_access_token(refresh_token)
    token = str(data.get("access_token", ""))
    if not token:
        raise RuntimeError("Gmail token refresh returned no access token")
    mailbox.access_token_encrypted = encrypt_secret(token)
    mailbox.token_expiry = now + timedelta(seconds=max(60, int(data.get("expires_in", 3600))))
    mailbox.is_connected = True
    db.commit()
    return token


def _collect_history_ids(
    extractor: GmailExtractor, state: GmailSyncState, *, bootstrap: bool
) -> tuple[list[str], str]:
    if bootstrap:
        profile = extractor.profile()
        history_id = str(profile.get("historyId", "") or "")
        days = max(1, min(int(settings.GMAIL_SYNC_LOOKBACK_DAYS), 90))
        after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y/%m/%d")
        listing = extractor.list_message_ids(query=f"after:{after}", max_results=200)
        ids = [str(item.get("id", "")) for item in listing.get("messages", []) if item.get("id")]
        return ids, history_id

    ids: list[str] = []
    page_token = ""
    history_id = state.history_id
    for _ in range(5):
        page = extractor.history(state.history_id, page_token=page_token, max_results=100)
        for entry in page.get("history", []) or []:
            for key in ("messagesAdded", "messages"):
                for item in entry.get(key, []) or []:
                    message_id = str(
                        (item.get("message") or {}).get("id", "") or item.get("id", "")
                    )
                    if message_id:
                        ids.append(message_id)
        history_id = str(page.get("historyId", "") or history_id)
        page_token = str(page.get("nextPageToken", "") or "")
        if not page_token:
            break
    return list(dict.fromkeys(ids)), history_id


def _normalize_message(
    mailbox: GoogleMailbox,
    full: dict[str, Any],
    *,
    gcs_bucket: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    headers = full.get("payload", {}).get("headers", []) or []
    subject = _header(headers, "Subject")
    sender = _header(headers, "From")
    sender_email = _sender_email(sender)
    recipients = _header(headers, "To")
    date = _header(headers, "Date")
    body = GmailExtractor._extract_body(full.get("payload", {}) or {})[:50_000]
    snippet = str(full.get("snippet", "") or "")[:1000]
    raw_attachments = GmailExtractor._extract_attachments(full.get("payload", {}) or {})
    text = f"{subject} {snippet} {body}"
    client = _client_for(sender_email, text)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    attachments: list[dict[str, Any]] = []
    for index, item in enumerate(raw_attachments):
        name = str(item.get("name", "") or "attachment")
        size = int(item.get("size") or 0)
        attachment_id = str(item.get("attachment_id", "") or "")
        attachments.append(
            {
                "name": name,
                "size": size,
                "mime_type": str(item.get("mime_type", "") or "application/octet-stream"),
                "attachment_id": attachment_id,
                "purpose": _attachment_purpose(name, subject, body),
                "gcs_path": "",
            }
        )

    message_id = str(full.get("id", "") or "")
    row = {
        "user_id": mailbox.user_id,
        "mailbox_id": mailbox.id,
        "message_id": message_id,
        "thread_id": str(full.get("threadId", "") or ""),
        "rfc822_message_id": _header(headers, "Message-ID"),
        "subject": subject[:512],
        "sender": sender[:320],
        "sender_email": sender_email[:320],
        "recipients": recipients,
        "date": date[:128],
        "internal_date": str(full.get("internalDate", "") or "")[:64],
        "intent": infer_intent(text),
        "client": client[:255],
        "context": text[:2000],
        "snippet": snippet,
        "body": body,
        "labels": [str(label) for label in (full.get("labelIds", []) or [])],
        "attachments": attachments,
        "gcs_processed_path": (
            f"{settings.GCS_PATH_GMAIL}gmail_processed/{today}/{_safe_name(message_id, 64)}.json"
        ),
    }
    return row, attachments


def sync_gmail_mailbox(db: Session, mailbox: GoogleMailbox, user: User | None = None) -> dict:
    """Run one bounded incremental sync for a connected Gmail mailbox."""
    token = gmail_access_token(db, mailbox)
    if not token:
        raise RuntimeError("Google mailbox is not authorized")

    state = db.query(GmailSyncState).filter(GmailSyncState.mailbox_id == mailbox.id).first()
    if state is None:
        state = GmailSyncState(
            user_id=mailbox.user_id,
            mailbox_id=mailbox.id,
            message_ids=[],
            stats={},
        )
        db.add(state)
        db.flush()

    extractor = GmailExtractor(token)
    message_ids, history_id = _collect_history_ids(
        extractor, state, bootstrap=not bool(state.history_id)
    )
    batch = max(1, min(int(settings.GMAIL_SYNC_BATCH), 100))
    message_ids = [item for item in message_ids if item not in set(state.message_ids or [])][:batch]

    gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_MAIL)
    created = updated = attachment_bytes = 0
    samples: list[dict[str, Any]] = []

    for message_id in message_ids:
        full = extractor.get_message(message_id)
        row, attachments = _normalize_message(mailbox, full, gcs_bucket=gcs.bucket_name)

        stored: list[dict[str, Any]] = []
        for item in attachments:
            attachment_id = str(item.get("attachment_id", "") or "")
            if attachment_id and int(item.get("size") or 0) <= int(
                settings.GMAIL_ATTACHMENT_MAX_BYTES
            ):
                try:
                    raw = extractor.get_attachment(message_id, attachment_id)
                    if raw:
                        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        path = (
                            f"{settings.GCS_PATH_GMAIL}attachments/{day}/"
                            f"gmail-{_safe_name(message_id, 40)}-{_safe_name(item['name'], 80)}"
                        )
                        if gcs.upload_bytes(path, raw, content_type=item["mime_type"]):
                            item["gcs_path"] = path
                            attachment_bytes += len(raw)
                except RuntimeError:
                    pass
            stored.append(item)
        row["attachments"] = stored

        existing = (
            db.query(GmailMessage)
            .filter(GmailMessage.mailbox_id == mailbox.id, GmailMessage.message_id == message_id)
            .first()
        )
        if existing is None:
            db.add(GmailMessage(**row))
            created += 1
        else:
            for key, value in row.items():
                setattr(existing, key, value)
            updated += 1

        if gcs.available:
            gcs.upload_json(row["gcs_processed_path"], {"mailbox": mailbox.email_address, **row})
        samples.append(
            {
                "message_id": message_id,
                "subject": row["subject"],
                "client": row["client"],
                "intent": row["intent"],
                "attachments": len(stored),
            }
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stats = dict(state.stats or {})
    daily = dict(stats.get("daily", {}))
    daily[today] = {
        "scanned": len(message_ids),
        "created": created,
        "updated": updated,
        "attachment_bytes": attachment_bytes,
    }
    stats["daily"] = daily
    state.history_id = history_id or state.history_id
    state.message_ids = list(dict.fromkeys([*message_ids, *(state.message_ids or [])]))[
        :_MAX_DEDUP_IDS
    ]
    state.stats = stats
    state.last_status = "ok"
    state.last_error = ""
    state.last_sync_at = datetime.now(timezone.utc)
    mailbox.last_checked_at = state.last_sync_at
    db.commit()
    return {
        "ok": True,
        "mailbox_id": mailbox.id,
        "email_address": mailbox.email_address,
        "scanned": len(message_ids),
        "created": created,
        "updated": updated,
        "attachments_stored": attachment_bytes,
        "history_id": state.history_id,
        "sample": samples[:10],
    }


def message_out(row: GmailMessage, *, include_body: bool = True) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "mailbox_id": row.mailbox_id,
        "message_id": row.message_id,
        "thread_id": row.thread_id,
        "subject": row.subject,
        "sender": row.sender,
        "sender_email": row.sender_email,
        "recipients": row.recipients,
        "date": row.date,
        "intent": row.intent,
        "client": row.client,
        "snippet": row.snippet,
        "labels": row.labels or [],
        "attachments": row.attachments or [],
        "gcs_processed_path": row.gcs_processed_path,
        "has_body": bool(row.body),
    }
    if include_body:
        payload["body"] = row.body
        payload["context"] = row.context
    return payload
