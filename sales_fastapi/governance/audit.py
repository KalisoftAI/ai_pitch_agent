"""Append-only audit trail.

Security-relevant actions (auth, contact changes, exports, model calls, secret
changes) are recorded with actor, resource, outcome and a redacted detail blob.
Details are always passed through PII redaction before they are persisted.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog
from .pii import redact_structured


def log_event(
    db: Session,
    *,
    action: str,
    actor_user_id: int | None = None,
    resource_type: str = "",
    resource_id: str = "",
    tenant_id: str = "",
    status: str = "success",
    ip_address: str = "",
    detail: dict[str, Any] | None = None,
    commit: bool = False,
) -> AuditLog:
    event = AuditLog(
        actor_user_id=actor_user_id or 0,
        action=action[:128],
        resource_type=resource_type[:64],
        resource_id=str(resource_id)[:128],
        tenant_id=tenant_id[:64],
        status=status[:32],
        ip_address=ip_address[:64],
        detail=redact_structured(detail or {}),
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    return event


def list_events(
    db: Session,
    *,
    actor_user_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
) -> list[AuditLog]:
    query = db.query(AuditLog)
    if actor_user_id is not None:
        query = query.filter(AuditLog.actor_user_id == actor_user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 500))).all()
