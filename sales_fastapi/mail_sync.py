"""Incremental IMAP sync orchestration -> GCS Kalika_gmail_data + checkpoints.

Flow
----
mailbox (IMAP UID, read-only)
    -> checkpoint dedup (UIDVALIDITY + last UID + Message-ID set)
    -> raw EML upload      Kalika_gmail_data/raw/YYYY-MM-DD/<uid>.eml
    -> attachment upload   Kalika_gmail_data/attachments/YYYY-MM-DD/<uid>-<file>
    -> processed JSON batch Kalika_gmail_data/processed/YYYY-MM-DD/sync-<ts>.json
    -> MailSyncState daily stats (fetched/processed) + SyncRun audit log

Retention (GCS objects only - the original mailbox is NEVER touched):
raw 180d, processed 365d, attachments 90d, sync logs 365d.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import settings
from .instore_mail import normalize_mail
from .models import EmailConnection, MailSyncState, SyncRun, User
from .security import decrypt_secret
from .services import EmailExtractor, GCSStorage

MAX_DEDUP_IDS = 2000
_DATE_FOLDER = re.compile(r"/(\d{4}-\d{2}-\d{2})/")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _mail_date(value: str) -> str:
    text = (value or "").strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S", "%a, %d %b %Y %H:%M %z", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:31], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else _today()


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "attachment")).strip("-")
    return (cleaned[:80] or "attachment")


def get_state(db, connection_id: int, user_id: int) -> MailSyncState:
    state = db.query(MailSyncState).filter(MailSyncState.connection_id == connection_id).first()
    if state is None:
        state = MailSyncState(connection_id=connection_id, user_id=user_id, mailbox="INBOX")
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def sync_connection(
    db,
    conn: EmailConnection,
    user: User,
    *,
    batch: int | None = None,
    full: bool = False,
    query: str = "",
    sender: str = "",
    since: datetime | None = None,
    until: datetime | None = None,
    unread_only: bool = False,
    before_uid: int | None = None,
) -> dict[str, Any]:
    """One incremental sync pass for a connection. Returns real counters."""
    state = get_state(db, conn.id, user.id)
    started = datetime.now(timezone.utc)
    run = SyncRun(job="email_sync", status="running", detail=f"connection={conn.id}")
    db.add(run)
    db.commit()
    db.refresh(run)

    password = decrypt_secret(conn.secret_encrypted)
    extractor = EmailExtractor(conn.imap_host, conn.imap_port, conn.email_address, password)
    counters = {
        "fetched": 0, "new": 0, "duplicates_skipped": 0,
        "raw_uploaded": 0, "processed_uploaded": 0, "attachments_uploaded": 0,
        "errors": [],
    }
    try:
        extractor.connect()
        uidvalidity = extractor.get_uidvalidity()
        reset = False
        if uidvalidity and state.uidvalidity and uidvalidity != state.uidvalidity:
            # mailbox rebuilt server-side: old UIDs are meaningless -> full resync window
            state.uidvalidity = uidvalidity
            state.last_uid = 0
            state.message_ids = []
            counters["errors"].append("UIDVALIDITY changed - checkpoint reset (no data loss, mail re-synced once)")
            reset = True
        if uidvalidity and not state.uidvalidity:
            state.uidvalidity = uidvalidity

        messages = extractor.sync_emails(
            last_uid=0 if (full or reset) else int(state.last_uid or 0),
            batch=batch or settings.MAIL_SYNC_BATCH,
            full=full,
            since=since,
            until=until,
            query=query,
            sender=sender,
            unread_only=unread_only,
            before_uid=before_uid,
        )
        gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_MAIL)
        base = settings.GCS_PATH_GMAIL
        processed: list[dict[str, Any]] = []
        known_ids = set(state.message_ids or [])
        max_uid = int(state.last_uid or 0)

        for message in messages:
            counters["fetched"] += 1
            uid = int(re.sub(r"\D", "", str(message.get("uid") or "0")) or 0)
            msg_id = str(message.get("message_id") or "")
            dedup_id = msg_id or f"uid:{conn.id}:{uid}"
            if uid and uid <= max_uid and not full and not reset:
                counters["duplicates_skipped"] += 1
                continue
            if dedup_id in known_ids:
                counters["duplicates_skipped"] += 1
                if uid > max_uid:
                    max_uid = uid  # never re-fetch a known duplicate on the next sync
                continue
            known_ids.add(dedup_id)
            counters["new"] += 1
            if uid > max_uid:
                max_uid = uid

            mail_day = _mail_date(str(message.get("date") or ""))
            raw = message.pop("_raw", b"") or b""
            attach_data = message.pop("_attachments_data", []) or []

            if gcs.available and raw:
                if gcs.upload_bytes(f"{base}raw/{mail_day}/uid{uid}.eml", raw, "message/rfc822"):
                    counters["raw_uploaded"] += 1
            for index, attachment in enumerate(attach_data):
                blob = f"{base}attachments/{mail_day}/uid{uid}-{index + 1}-{_safe_name(attachment['name'])}"
                if gcs.available and gcs.upload_bytes(blob, attachment["data"], attachment.get("mime_type") or "application/octet-stream"):
                    counters["attachments_uploaded"] += 1
            record = normalize_mail(
                {
                    "uid": str(uid),
                    "subject": message.get("subject", ""),
                    "from": message.get("from", ""),
                    "to": message.get("to", ""),
                    "date": message.get("date", ""),
                    "body": message.get("body", ""),
                    "snippet": message.get("snippet", ""),
                    "intent": message.get("intent", ""),
                    "attachments": message.get("attachments", []),
                },
                source="imap",
            )
            record["connection_id"] = conn.id
            record["message_id"] = msg_id
            record["attachment_count"] = len(attach_data)
            processed.append({**{k: v for k, v in record.items() if k != "body"}, "body_preview": record.get("body", "")[:1500]})

        counters["new_records"] = processed  # caller may trim before responding
        if processed and gcs.available:
            batch_name = f"{base}processed/{_today()}/sync-{started.strftime('%H%M%S')}.json"
            payload = {"connection_id": conn.id, "email": conn.email_address, "generated_at": started.isoformat(), "mails": processed}
            if gcs.upload_json(batch_name, payload):
                counters["processed_uploaded"] = len(processed)
                state.gcs_last_prefix = batch_name

        state.last_uid = max_uid
        state.message_ids = list(known_ids)[-MAX_DEDUP_IDS:]
        daily = dict(state.stats or {})
        day_stats = dict((daily.get("daily") or {}).get(_today()) or {})
        day_stats["fetched"] = int(day_stats.get("fetched", 0)) + counters["fetched"]
        day_stats["new"] = int(day_stats.get("new", 0)) + counters["new"]
        day_stats["processed"] = int(day_stats.get("processed", 0)) + counters["new"]
        day_stats["duplicates_skipped"] = int(day_stats.get("duplicates_skipped", 0)) + counters["duplicates_skipped"]
        daily["daily"] = {**(daily.get("daily") or {}), _today(): day_stats}
        state.stats = daily
        state.last_sync_at = datetime.now(timezone.utc)
        state.last_status = "ok" if not counters["errors"] else "ok_with_warnings"
        state.last_error = "; ".join(counters["errors"])[:500]
        conn.is_connected = True
        conn.last_checked_at = datetime.now(timezone.utc)
        run.status = "ok"
        run.detail = json.dumps({k: v for k, v in counters.items() if k != "new_records"})
        run.finished_at = datetime.now(timezone.utc)
    except Exception as exc:  # noqa: BLE001 - surface as structured error
        state.last_status = "error"
        state.last_error = f"{type(exc).__name__}: {exc}"[:500]
        run.status = "error"
        run.detail = str(exc)[:1000]
        run.finished_at = datetime.now(timezone.utc)
        counters["errors"].append(str(exc)[:300])
    finally:
        extractor.disconnect()
        db.commit()

    result = {k: v for k, v in counters.items() if k != "new_records"}
    result["sample"] = [
        {k: v for k, v in item.items() if k in ("id", "subject", "from_email", "date", "intent", "company", "client_name", "outcome")}
        for item in processed[:10]
    ] if processed else []
    result["checkpoint"] = {
        "last_uid": int(state.last_uid or 0),
        "uidvalidity": int(state.uidvalidity or 0),
        "dedup_ids": len(state.message_ids or []),
        "next_before_uid": min([int(m.get("uid") or 0) for m in messages], default=0) if messages else 0,
    }
    result["gcs_available"] = GCSStorage(bucket_name=settings.GCS_BUCKET_MAIL).available
    result["status"] = state.last_status
    return result


def cleanup_retention(db) -> dict[str, Any]:
    """Delete expired GCS mail objects + stale sync-log rows. Mailbox untouched."""
    removed = {"raw": 0, "processed": 0, "attachments": 0, "logs": 0}
    errors: list[str] = []
    gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_MAIL)
    base = settings.GCS_PATH_GMAIL
    rules = [
        ("raw", settings.MAIL_RETENTION_RAW_DAYS),
        ("processed", settings.MAIL_RETENTION_PROCESSED_DAYS),
        ("attachments", settings.MAIL_RETENTION_ATTACHMENTS_DAYS),
    ]
    if gcs.available and gcs._client is not None:

        client: Any = gcs._client
        bucket = client.bucket(gcs.bucket_name)
        now = datetime.now(timezone.utc).date()
        for folder, days in rules:
            cutoff = now - timedelta(days=int(days))
            try:
                for blob in client.list_blobs(gcs.bucket_name, prefix=f"{base}{folder}/"):
                    match = _DATE_FOLDER.search("/" + blob.name[len(base):])
                    if not match:
                        continue
                    try:
                        blob_day = datetime.strptime(match.group(1), "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    if blob_day < cutoff:
                        try:
                            bucket.blob(blob.name).delete()
                            removed[folder] += 1
                        except Exception as exc:  # noqa: BLE001
                            errors.append(f"{blob.name}: {exc}"[:200])
            except Exception as exc:  # noqa: BLE001
                errors.append(f"list {folder}: {exc}"[:200])
    else:
        errors.append("GCS unavailable - retention skipped")
    # DB sync-log rows older than retention (audit history kept via AuditLog separately)
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(settings.MAIL_RETENTION_LOGS_DAYS))
    deleted = db.query(SyncRun).filter(SyncRun.job.in_(("email_sync", "mail_retention")), SyncRun.started_at < cutoff).delete()
    removed["logs"] = int(deleted or 0)
    db.commit()
    run = SyncRun(job="mail_retention", status="ok" if not errors else "error", detail=json.dumps({"removed": removed, "errors": errors[:5]}))
    db.add(run)
    db.commit()
    return {"removed": removed, "errors": errors[:5], "mail_touched": False}
