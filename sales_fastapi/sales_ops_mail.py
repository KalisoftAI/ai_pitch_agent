"""Read-only Instor India mail capture for the isolated Sales Ops module.

The mailbox is never modified: messages are fetched with the existing
``EmailExtractor`` (UID SEARCH + BODY.PEEK), matched against the Instor sender
allowlist, summarised through the guarded ``ModelRouter``, and stored in the
Sales Ops-only tables. A per-mailbox checkpoint walks older mail in batches so
the first sync backfills history and later syncs only look for new UIDs.
"""

from __future__ import annotations

import hashlib
import imaplib
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any

from sqlalchemy.orm import Session

from .config import settings
from .governance.audit import log_event
from .llm.router import ModelRouter
from .models import SalesOpsIncomingMail, SalesOpsMailSyncState
from .services import EmailExtractor, GCSStorage, compact_text

COMPANY_NAME = "Instor India Pvt. Ltd."
COMPANY_ADDRESS = "New Gat 584/2, Koregaon Bhima, Taluka Shirur, Pune – 412216, India."
DEFAULT_MAILBOX = "kalikaenterprises@gmail.com"
IST = timezone(timedelta(hours=5, minutes=30))
_KNOWN_SENDERS = {"rpatil@instorindia.com"}  # from the existing instore client directory
_KNOWN_DOMAINS = {"instorindia.com"}
_MAX_PAGES = 20
_FETCH_WINDOW_BYTES = 400_000  # stays below imaplib's 1 MB per-line ceiling
_INSTOR_SEARCH = "instor"  # matches the known domain and "Instor" display names server-side


class _BoundedIMAP4_SSL(imaplib.IMAP4_SSL):
    """IMAP client that asks for a bounded slice of each message body."""

    def uid(self, command, *args):
        safe_args = tuple(
            re.sub(
                r"BODY\.PEEK\[\]",
                f"BODY.PEEK[]<0.{_FETCH_WINDOW_BYTES}>",
                arg,
            )
            if isinstance(arg, str)
            else arg
            for arg in args
        )
        return super().uid(command, *safe_args)


class SalesOpsEmailExtractor(EmailExtractor):
    """Sales Ops-only extractor: same read-only logic, safer large-message fetch."""

    def connect(self) -> bool:
        self.connection = _BoundedIMAP4_SSL(self.imap_host, self.imap_port)
        self.connection.login(self.user, self.password)
        self.connection.select("INBOX")
        return True


def _csv_values(value: str | None) -> list[str]:
    return [item.strip().lower() for item in str(value or "").split(",") if item.strip()]


def _sender_rules() -> tuple[set[str], set[str]]:
    emails = set(_KNOWN_SENDERS)
    domains = set(_KNOWN_DOMAINS)
    for item in _csv_values(settings.SALES_OPS_INSTOR_SENDERS):
        if "@" in item:
            emails.add(item)
        else:
            domains.add(item.lstrip("@"))
    return emails, domains


def is_instor_sender(from_header: str) -> bool:
    """Match a From header against Instor addresses, domains or display names."""
    name, address = parseaddr(from_header or "")
    if not address and "@" in (from_header or ""):
        address = from_header.strip()
    address = address.strip().lower()
    domain = address.rsplit("@", 1)[-1] if "@" in address else ""
    emails, domains = _sender_rules()
    if address in emails or domain in domains:
        return True
    # Display names and RFC-822 comments are not always returned by parseaddr,
    # so also check the raw header for an "Instor" token.
    raw_header = re.sub(r"\s+", " ", str(from_header or "")).strip().lower()
    return bool(re.search(r"\binstor\b", raw_header))


def _received_at(value: str) -> datetime:
    """Return a naive Asia/Kolkata datetime for date-wise/time-wise grouping."""
    try:
        parsed = parsedate_to_datetime(value or "")
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        return datetime.now(IST).replace(tzinfo=None)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(IST).replace(tzinfo=None)


def _dedup_key(message: dict[str, Any], mailbox: str) -> str:
    message_id = str(message.get("message_id") or "").strip()
    if message_id:
        seed = message_id
    else:
        seed = "|".join(
            str(message.get(field) or "")
            for field in ("from", "date", "subject", "uid")
        )
    return hashlib.sha256(f"{mailbox}|{seed}".encode("utf-8")).hexdigest()[:64]


def _credentials() -> tuple[str, str]:
    """Resolve the configured mailbox, defaulting to the kalika2 Gmail account."""
    address = str(settings.SALES_OPS_INSTOR_MAILBOX or "").strip()
    password = str(settings.SALES_OPS_INSTOR_APP_PASSWORD or "").strip()
    default_address, default_password = "", ""
    try:
        default_address, default_password = settings.gmail_credentials_for_key("kalika", "kalika2")
    except ValueError:
        pass
    if not address:
        return default_address.strip(), default_password.strip()
    if not password and address.lower() == default_address.strip().lower():
        password = default_password.strip()
    return address, password


def _state(db: Session, mailbox: str) -> SalesOpsMailSyncState:
    row = (
        db.query(SalesOpsMailSyncState)
        .filter(SalesOpsMailSyncState.mailbox == mailbox)
        .first()
    )
    if row is None:
        row = SalesOpsMailSyncState(mailbox=mailbox)
        db.add(row)
        db.flush()
    return row


def auto_sync_due(db: Session, interval_seconds: int = 300) -> bool:
    """Throttle implicit refreshes so opening the tab cannot hammer IMAP."""
    mailbox, password = _credentials()
    if not mailbox or not password:
        return False
    row = (
        db.query(SalesOpsMailSyncState)
        .filter(SalesOpsMailSyncState.mailbox == mailbox)
        .first()
    )
    if row is None or row.last_sync_at is None:
        return True
    elapsed = (datetime.utcnow() - row.last_sync_at).total_seconds()
    return elapsed >= max(30, int(interval_seconds))


def _extractive_summary(subject: str, body: str) -> str:
    text = compact_text(body or "", 1200)
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if len(part.strip()) >= 12]
    picked: list[str] = []
    for sentence in sentences:
        picked.append(sentence)
        if sum(len(part) for part in picked) >= 280:
            break
    summary = " ".join(picked)[:420].strip()
    return summary or (compact_text(subject, 160) or "No message body was provided.")


def _summarize_email(
    subject: str, sender_email: str, body: str, *, user_id: int = 0, db: Session | None = None
) -> tuple[str, str]:
    """Summarise one mail via ModelRouter, with an honest offline fallback."""
    prompt = (
        "Summarize this incoming email for Kalika Enterprises sales ops. "
        "Use at most three short sentences or bullets. Keep product names, "
        "quantities, rates, dates and requested actions. Never invent facts.\n"
        f"Subject: {compact_text(subject, 300)}\n"
        f"From: {compact_text(sender_email, 200)}\n"
        f"Email body: {compact_text(body, 4000)}\n"
        "Summary:"
    )
    try:
        routed = ModelRouter(config=None, db=db).run(
            "sales_ops_email_summary",
            prompt,
            system=(
                "You are a careful B2B packaging sales assistant. Summarize only "
                "the supplied email; do not invent numbers or commitments."
            ),
            user_id=user_id or None,
            db=db,
        )
        text = (routed.result.text or "").strip()
        if routed.result.provider != "echo" and text:
            return text[:2000], f"llm:{routed.result.provider}/{routed.result.model}"
    except Exception:  # noqa: BLE001 - mail capture must not fail because an LLM is offline
        pass
    return _extractive_summary(subject or "", body or ""), "deterministic_fallback"


def _append_jsonl(blob_name: str, payload: dict[str, Any]) -> str:
    storage = GCSStorage(bucket_name=settings.GCS_BUCKET_CRM or "sales-crm")
    if not storage.available or storage._client is None:
        return ""
    try:
        bucket = storage._client.bucket(storage.bucket_name)
        blob = bucket.blob(blob_name)
        existing = (
            blob.download_as_bytes().decode("utf-8", errors="replace") if blob.exists() else ""
        )
        blob.upload_from_string(
            f"{existing}{json.dumps(payload, ensure_ascii=False, default=str)}\n",
            content_type="application/x-ndjson",
        )
        return f"gs://{storage.bucket_name}/{blob_name}"
    except Exception:  # noqa: BLE001 - GCS is optional for this isolated path
        return ""


def sync_instor_mails(
    db: Session,
    *,
    user_id: int = 0,
    actor: str = "",
    limit: int | None = None,
) -> dict[str, Any]:
    """Fetch a read-only batch of Instor mail, summarise new messages, persist them."""
    mailbox, password = _credentials()
    mailbox = mailbox or DEFAULT_MAILBOX
    if not password:
        return {
            "status": "not_configured",
            "mailbox": mailbox,
            "scanned": 0,
            "matched": 0,
            "new": 0,
            "duplicate": 0,
            "reason": "Gmail app password is not configured for this mailbox",
        }

    batch = max(20, min(int(limit or settings.SALES_OPS_INSTOR_SYNC_LIMIT or 25), 50))
    state = _state(db, mailbox)
    messages: list[dict[str, Any]] = []
    fetch_error = ""
    extractor = SalesOpsEmailExtractor(
        (settings.IMAP_HOST or "imap.gmail.com").strip(),
        int(settings.IMAP_PORT or 993),
        mailbox,
        password,
    )
    try:
        extractor.connect()
        # Search Instor on the server so the first sync backfills the whole
        # history instead of crawling every unrelated message in the mailbox.
        if not state.backfill_complete:
            page_cursor: int | None = state.cursor_uid or None
            for _ in range(_MAX_PAGES):
                page = extractor.sync_emails(
                    full=True, batch=batch, before_uid=page_cursor, query=_INSTOR_SEARCH
                )
                if not page:
                    state.backfill_complete = True
                    break
                messages.extend(page)
                page_uids = [
                    int(item["uid"]) for item in page if str(item.get("uid") or "").isdigit()
                ]
                if page_uids:
                    page_cursor = min(page_uids)
                if len(page) < batch:
                    state.backfill_complete = True
                    break

        # Walk forward-only new UIDs (paged) so no new mail is skipped on busy days.
        page_cursor = None
        if int(state.last_uid or 0) > 0:
            for _ in range(_MAX_PAGES):
                page = extractor.sync_emails(
                    last_uid=int(state.last_uid),
                    batch=batch,
                    before_uid=page_cursor,
                    query=_INSTOR_SEARCH,
                )
                if not page:
                    break
                messages.extend(page)
                if len(page) < batch:
                    break
                page_cursor = min(int(item["uid"]) for item in page)
    except Exception as exc:  # noqa: BLE001 - offline mailbox must not break Sales Ops
        fetch_error = str(exc)[:300]
    finally:
        extractor.disconnect()

    if fetch_error:
        state.last_status = "error"
        state.last_error = fetch_error
        db.commit()
        return {
            "status": "error",
            "mailbox": mailbox,
            "scanned": 0,
            "matched": 0,
            "new": 0,
            "duplicate": 0,
            "error": fetch_error,
        }

    by_uid: dict[str, dict[str, Any]] = {}
    for message in messages:
        by_uid[str(message.get("uid") or _dedup_key(message, mailbox))] = message
    unique_messages = list(by_uid.values())

    existing_keys = {
        row[0]
        for row in db.query(SalesOpsIncomingMail.dedup_key)
        .filter(SalesOpsIncomingMail.mailbox == mailbox)
        .all()
    }
    matched = 0
    created = 0
    for message in unique_messages:
        if not is_instor_sender(str(message.get("from") or "")):
            continue
        matched += 1
        dedup_key = _dedup_key(message, mailbox)
        if dedup_key in existing_keys:
            continue
        existing_keys.add(dedup_key)
        sender_name, sender_email = parseaddr(str(message.get("from") or ""))
        subject = str(message.get("subject") or "")
        body = str(message.get("body") or "")
        summary, summary_source = _summarize_email(
            subject, sender_email, body, user_id=user_id, db=db
        )
        received = _received_at(str(message.get("date") or ""))
        blob_name = (
            f"{settings.GCS_PATH_SALES_APP_DATA.strip('/')}/sales_ops_mail/instor/"
            f"{received.strftime('%Y-%m-%d')}.jsonl"
        )
        gcs_uri = _append_jsonl(
            blob_name,
            {
                "mailbox": mailbox,
                "company": COMPANY_NAME,
                "sender": str(message.get("from") or ""),
                "subject": subject,
                "received_at": received.isoformat(),
                "ai_summary": summary,
                "summary_source": summary_source,
                "created_by": actor,
            },
        )
        db.add(
            SalesOpsIncomingMail(
                mailbox=mailbox,
                company=COMPANY_NAME,
                sender_name=(sender_name or sender_email or "Unknown sender")[:255],
                sender_email=sender_email[:320],
                sender_raw=str(message.get("from") or "")[:512],
                subject=subject[:512],
                received_at=received,
                received_date=received.strftime("%Y-%m-%d"),
                received_time=received.strftime("%H:%M"),
                body_snippet=compact_text(body, 600),
                ai_summary=summary,
                summary_source=summary_source,
                message_id=str(message.get("message_id") or "")[:512],
                imap_uid=str(message.get("uid") or "")[:32],
                dedup_key=dedup_key,
                gcs_uri=gcs_uri,
                created_by=actor[:255],
            )
        )
        created += 1

    uids = [int(item["uid"]) for item in unique_messages if str(item.get("uid") or "").isdigit()]
    if uids:
        state.last_uid = max(int(state.last_uid or 0), max(uids))
    state.fetched_total = int(state.fetched_total or 0) + len(unique_messages)
    state.new_total = int(state.new_total or 0) + created
    state.last_sync_at = datetime.utcnow()
    state.last_status = "ok"
    state.last_error = ""
    log_event(
        db,
        action="sales_ops_instor_mail_sync",
        actor_user_id=user_id or 0,
        resource_type="sales_ops_incoming_mail",
        resource_id=mailbox,
        detail={
            "scanned": len(unique_messages),
            "matched": matched,
            "new": created,
            "backfill_complete": bool(state.backfill_complete),
        },
    )
    db.commit()
    return {
        "status": "ok",
        "mailbox": mailbox,
        "company": COMPANY_NAME,
        "scanned": len(unique_messages),
        "matched": matched,
        "new": created,
        "duplicate": matched - created,
        "backfill_complete": bool(state.backfill_complete),
        "last_uid": int(state.last_uid or 0),
        "last_sync_at": state.last_sync_at.isoformat(),
    }


def list_instor_mails(db: Session, *, limit: int = 200, date_filter: str = "") -> dict[str, Any]:
    """Return Instor mail records grouped by received date and time."""
    query = db.query(SalesOpsIncomingMail).filter(SalesOpsIncomingMail.company == COMPANY_NAME)
    if date_filter:
        query = query.filter(SalesOpsIncomingMail.received_date == str(date_filter)[:10])
    rows = (
        query.order_by(SalesOpsIncomingMail.received_at.desc(), SalesOpsIncomingMail.id.desc())
        .limit(max(1, min(int(limit or 200), 500)))
        .all()
    )
    groups: list[dict[str, Any]] = []
    by_date: dict[str, dict[str, Any]] = {}
    for row in rows:
        day = row.received_date or str(row.received_at)[:10]
        if day not in by_date:
            by_date[day] = {"date": day, "count": 0, "messages": []}
            groups.append(by_date[day])
        by_date[day]["count"] += 1
        by_date[day]["messages"].append(
            {
                "id": row.id,
                "sender_name": row.sender_name,
                "sender_email": row.sender_email,
                "sender_raw": row.sender_raw,
                "subject": row.subject,
                "received_date": row.received_date,
                "received_time": row.received_time,
                "ai_summary": row.ai_summary,
                "summary_source": row.summary_source,
                "body_snippet": row.body_snippet,
                "gcs_uri": row.gcs_uri,
            }
        )
    return {
        "company": {"name": COMPANY_NAME, "address": COMPANY_ADDRESS},
        "mailbox": _credentials()[0] or DEFAULT_MAILBOX,
        "total": len(rows),
        "groups": groups,
    }
