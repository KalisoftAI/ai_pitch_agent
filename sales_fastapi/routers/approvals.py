"""Subtask approvals with human acceptance + confidence (future-scope review).

The cost-effective LLM chain (Gemma -> Gemini-Flash) proposes data-refinement
subtasks; each carries a model confidence score and stays ``pending`` until a
human (ai.solutions admin) accepts or rejects it. This is the human-in-the-loop
gate that keeps automated processing aligned and auditable.

Endpoints
    GET  /api/approvals            – list subtasks (admin sees all, others own)
    POST /api/approvals            – propose a subtask (user or system)
    POST /api/approvals/generate   – LLM proposes refined subtasks (admin)
    POST /api/approvals/{id}/decide– approve / reject (admin only)
    GET  /api/approvals/issues     – issues log (admin only): sync + audit errors
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..governance.audit import log_event
from ..models import AuditLog, SyncRun, TaskApproval, User
from ..security import get_current_user, is_admin_user, require_admin

router = APIRouter(prefix="/approvals", tags=["approvals"])


# ------------------------------------------------------------------ schemas
class ApprovalIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    area: str = Field(default="general", max_length=64)
    detail: str = Field(default="", max_length=5000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DecideIn(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")


def _out(row: TaskApproval) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "title": row.title,
        "area": row.area,
        "detail": row.detail,
        "confidence": round(row.confidence or 0.0, 3),
        "source": row.source,
        "status": row.status,
        "decided_by": row.decided_by,
        "decided_at": str(row.decided_at) if row.decided_at else None,
        "created_at": str(row.created_at),
    }


# ------------------------------------------------------------------ list
@router.get("")
def list_approvals(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(TaskApproval)
    if not is_admin_user(user):
        query = query.filter(TaskApproval.user_id == user.id)
    if status:
        query = query.filter(TaskApproval.status == status)
    rows = query.order_by(TaskApproval.id.desc()).limit(200).all()
    pending = (
        db.query(TaskApproval).filter(TaskApproval.status == "pending").count()
        if is_admin_user(user)
        else db.query(TaskApproval)
        .filter(TaskApproval.user_id == user.id, TaskApproval.status == "pending")
        .count()
    )
    return {"pending": pending, "items": [_out(r) for r in rows]}


# ------------------------------------------------------------------ create
@router.post("", status_code=201)
def create_approval(
    payload: ApprovalIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = TaskApproval(
        user_id=user.id,
        title=payload.title,
        area=payload.area,
        detail=payload.detail,
        confidence=payload.confidence,
        source="user",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_event(
        db,
        action="approval.create",
        actor_user_id=user.id,
        resource_type="task_approval",
        resource_id=str(row.id),
        tenant_id=user.domain,
        detail={"title": row.title, "confidence": row.confidence},
        commit=True,
    )
    return _out(row)


# ------------------------------------------------------------------ LLM proposals
@router.post("/generate")
def generate_approvals(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Propose refined data subtasks using the cost-effective Gemma/Flash chain.

    Falls back to deterministic rule-based proposals when no LLM provider is
    available, so the review queue is never empty.
    """
    from ..erp_sync import dispatch_stats, latest_report_date
    from ..tally_sync import tally_stats

    day = latest_report_date(db)
    dispatch = dispatch_stats(db, day) if day else {}
    tally = tally_stats(db)

    facts = {
        "erp_report_date": day or "none",
        "dispatch_records": dispatch.get("records", 0),
        "dispatch_completion_pct": dispatch.get("completion_pct", 0),
        "tally_available": tally.get("data_available", False),
        "tally_customers": tally.get("customers", 0),
    }

    proposals: list[dict] = []
    # Try the cost-optimised LLM router (Gemma first, Gemini-Flash fallback).
    try:
        from ..llm.router import ModelRouter

        prompt = (
            "You are an operations planner for a packaging-materials sales team. "
            "Given these live facts, propose up to 3 concrete data-refinement "
            "subtasks as JSON: a list of objects with keys "
            "title, area, detail, confidence (0-1).\n\n"
            f"facts = {facts}"
        )
        route = ModelRouter().run(
            "research_synthesis", prompt, user_id=admin.id, db=db, temperature=0.3
        )
        import json
        import re

        text = route.result.text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            for item in json.loads(match.group(0))[:3]:
                proposals.append(
                    {
                        "title": str(item.get("title", ""))[:255],
                        "area": str(item.get("area", "llm"))[:64],
                        "detail": str(item.get("detail", ""))[:5000],
                        "confidence": float(item.get("confidence", 0.5)),
                        "source": "llm",
                    }
                )
    except Exception:  # noqa: BLE001 - fall through to deterministic proposals
        proposals = []

    if not proposals:
        # Deterministic, data-driven proposals (no LLM cost).
        if not day:
            proposals.append(
                {
                    "title": "Sync latest ERP dispatch report",
                    "area": "erp",
                    "detail": "No ERP report synced yet. Run sync_all to pull ERP-V1/Reports.",
                    "confidence": 0.9,
                    "source": "system",
                }
            )
        if dispatch.get("completion_pct", 100) < 70:
            proposals.append(
                {
                    "title": "Follow up partially-dispatched orders",
                    "area": "dispatch",
                    "detail": f"Delivery completion is {dispatch.get('completion_pct', 0)}%.",
                    "confidence": 0.8,
                    "source": "system",
                }
            )
        if not tally.get("data_available"):
            proposals.append(
                {
                    "title": "Sync Tally sales registers",
                    "area": "tally",
                    "detail": "No Tally data available. Run sync_all.",
                    "confidence": 0.85,
                    "source": "system",
                }
            )

    created = []
    for p in proposals:
        row = TaskApproval(
            user_id=admin.id,
            title=p["title"] or "Untitled subtask",
            area=p["area"],
            detail=p["detail"],
            confidence=max(0.0, min(1.0, p["confidence"])),
            source=p["source"],
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    log_event(
        db,
        action="approval.generate",
        actor_user_id=admin.id,
        resource_type="task_approval",
        tenant_id=admin.domain,
        detail={"created": len(created)},
        commit=True,
    )
    return {"created": len(created), "items": [_out(r) for r in created]}


# ------------------------------------------------------------------ decide
@router.post("/{approval_id}/decide")
def decide_approval(
    approval_id: int,
    payload: DecideIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(TaskApproval).filter(TaskApproval.id == approval_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Subtask not found")
    row.status = "approved" if payload.action == "approve" else "rejected"
    row.decided_by = admin.email or ""
    row.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    log_event(
        db,
        action=f"approval.{payload.action}",
        actor_user_id=admin.id,
        resource_type="task_approval",
        resource_id=str(row.id),
        tenant_id=admin.domain,
        detail={"title": row.title},
        commit=True,
    )
    return _out(row)


# ------------------------------------------------------------------ issues log
@router.get("/issues")
def issues_log(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """ai.solutions-only activity/issues log: sync failures + audit errors."""
    sync_failures = (
        db.query(SyncRun)
        .filter(SyncRun.status != "ok")
        .order_by(SyncRun.id.desc())
        .limit(30)
        .all()
    )
    audit_errors = (
        db.query(AuditLog)
        .filter(AuditLog.status.notin_(("success", "dry_run")))
        .order_by(AuditLog.id.desc())
        .limit(30)
        .all()
    )
    return {
        "sync_failures": [
            {
                "id": r.id,
                "job": r.job,
                "status": r.status,
                "detail": (r.detail or "")[:300],
                "finished_at": str(r.finished_at) if r.finished_at else None,
            }
            for r in sync_failures
        ],
        "audit_errors": [
            {
                "id": e.id,
                "action": e.action,
                "status": e.status,
                "resource_type": e.resource_type,
                "created_at": str(e.created_at),
            }
            for e in audit_errors
        ],
    }
