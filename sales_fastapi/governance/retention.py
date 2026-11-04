"""Retention policy and purge helpers.

Retention is expressed in days per logical dataset. ``purge`` deletes rows older
than the policy cutoff and is dry-run by default so it is safe to call from a
scheduled job or an admin endpoint.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuditLog, Contact

_RETENTION_DAYS: dict[str, int] = {
    "audit_logs": settings.RETENTION_DAYS_AUDIT,
    "contacts": settings.RETENTION_DAYS_CONTACTS,
}


def policy() -> dict[str, int]:
    return dict(_RETENTION_DAYS)


def cutoff(days: int, *, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now - timedelta(days=days)


def purge(db: Session, *, dry_run: bool = True) -> dict[str, Any]:
    """Delete rows older than the retention window. Never touches ``users``."""
    now = datetime.now(timezone.utc)
    result: dict[str, Any] = {"dry_run": dry_run, "deleted": {}}

    audit_cutoff = cutoff(_RETENTION_DAYS["audit_logs"], now=now)
    audit_query = db.query(AuditLog).filter(AuditLog.created_at < audit_cutoff)
    result["deleted"]["audit_logs"] = audit_query.count()
    if not dry_run:
        audit_query.delete(synchronize_session=False)

    contact_cutoff = cutoff(_RETENTION_DAYS["contacts"], now=now)
    contact_query = db.query(Contact).filter(Contact.created_at < contact_cutoff)
    result["deleted"]["contacts"] = contact_query.count()
    if not dry_run:
        contact_query.delete(synchronize_session=False)

    if not dry_run:
        db.commit()
    return result
