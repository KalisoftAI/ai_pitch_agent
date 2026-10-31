"""Internal team chat — daily rate reviews + field-executive updates.

Flow (voice-enabled field update):
1. Field executive records a voice note on mobile -> /api/voice/transcribe
2. The transcript is posted here as a ``field_update`` with status ``pending``
3. Sales executive reviews and uses the two-option control: approve / reject
4. Approved updates become visible to the whole team; rejected ones are marked.

Rate review: sales posts a ``rate_review`` message each day with the calculated
rate so the internal team can review and comment in the same thread list.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TeamMessage, User, VoiceTranscript
from ..security import get_current_user

router = APIRouter(prefix="/team", tags=["team"])


class TeamMessageIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)
    kind: Literal["general", "rate_review", "field_update"] = "general"
    transcript_id: int = 0
    meta: dict = Field(default_factory=dict)


class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]


def _out(m: TeamMessage) -> dict:
    return {
        "id": m.id, "kind": m.kind, "body": m.body, "status": m.status,
        "author_name": m.author_name, "author_role": m.author_role,
        "transcript_id": m.transcript_id, "meta": m.meta or {},
        "reviewed_by": m.reviewed_by, "reviewed_at": str(m.reviewed_at) if m.reviewed_at else None,
        "created_at": str(m.created_at),
    }


@router.get("/messages")
def list_messages(kind: str | None = None, status: str | None = None,
                  limit: int = Query(default=100, ge=1, le=500),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(TeamMessage)
    if kind:
        q = q.filter(TeamMessage.kind == kind)
    if status:
        q = q.filter(TeamMessage.status == status)
    rows = q.order_by(TeamMessage.id.desc()).limit(limit).all()
    return {"messages": [_out(m) for m in rows],
            "pending_count": db.query(TeamMessage).filter(TeamMessage.status == "pending").count()}


@router.post("/messages")
def post_message(payload: TeamMessageIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    # Field updates from voice notes start as "pending" — the two-option approval
    # (approve / reject) happens via /team/messages/{id}/review.
    initial = "pending" if payload.kind == "field_update" else "posted"

    transcript_text = ""
    if payload.transcript_id:
        t = db.query(VoiceTranscript).filter(VoiceTranscript.id == payload.transcript_id).first()
        if t is None:
            raise HTTPException(status_code=404, detail="Transcript not found")
        transcript_text = (t.transcript or "")[:2000]

    msg = TeamMessage(
        user_id=user.id,
        author_name=user.name or user.email.split("@")[0],
        author_role="field" if payload.kind == "field_update" else "sales",
        kind=payload.kind,
        body=payload.body.strip() or transcript_text,
        transcript_id=payload.transcript_id,
        meta={**(payload.meta or {}), **({"transcript": transcript_text} if transcript_text else {})},
        status=initial,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _out(msg)


@router.post("/messages/{message_id}/review")
def review_message(message_id: int, payload: ReviewIn,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Two-option approval: approve -> visible to team, reject -> marked rejected."""
    msg = db.query(TeamMessage).filter(TeamMessage.id == message_id).first()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.status != "pending":
        raise HTTPException(status_code=409, detail=f"Already reviewed ({msg.status})")
    msg.status = payload.decision
    msg.reviewed_by = user.name or user.email
    msg.reviewed_at = datetime.utcnow()
    db.commit()
    return _out(msg)


@router.get("/rate-today")
def rate_today(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Latest rate_review message of the day + count (for the daily review strip)."""
    rows = (db.query(TeamMessage).filter(TeamMessage.kind == "rate_review")
            .order_by(TeamMessage.id.desc()).limit(5).all())
    return {"recent_rate_reviews": [_out(m) for m in rows], "count": len(rows)}
