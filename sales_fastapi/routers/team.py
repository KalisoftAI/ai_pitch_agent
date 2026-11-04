from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TeamMessage, User, VoiceTranscript
from ..security import get_current_user, is_admin_user

router = APIRouter(prefix="/team", tags=["team"])


class TeamMessageIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)
    kind: Literal["general", "rate_review", "field_update"] = "general"
    transcript_id: int = 0
    meta: dict = Field(default_factory=dict)


class TeamMessageUpdate(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)
    meta: dict | None = None


class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]


def _out(m: TeamMessage) -> dict:
    return {
        "id": m.id,
        "user_id": m.user_id,
        "kind": m.kind,
        "body": m.body,
        "status": m.status,
        "author_name": m.author_name,
        "author_role": m.author_role,
        "transcript_id": m.transcript_id,
        "meta": m.meta or {},
        "reviewed_by": m.reviewed_by,
        "reviewed_at": str(m.reviewed_at) if m.reviewed_at else None,
        "created_at": str(m.created_at),
    }


def _can_manage(message: TeamMessage, user: User) -> bool:
    return is_admin_user(user) or message.user_id == user.id


@router.get("/messages")
def list_messages(
    kind: str | None = None,
    status: str | None = None,
    mine: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(TeamMessage)
    if kind:
        q = q.filter(TeamMessage.kind == kind)
    if status:
        q = q.filter(TeamMessage.status == status)
    if mine:
        q = q.filter(TeamMessage.user_id == user.id)
    rows = q.order_by(TeamMessage.id.desc()).limit(limit).all()
    return {
        "messages": [_out(m) for m in rows],
        "pending_count": db.query(TeamMessage).filter(TeamMessage.status == "pending").count(),
        "mine_count": db.query(TeamMessage).filter(TeamMessage.user_id == user.id).count(),
    }


@router.post("/messages")
def post_message(
    payload: TeamMessageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    initial = "pending" if payload.kind == "field_update" else "posted"

    transcript_text = ""
    if payload.transcript_id:
        t = (
            db.query(VoiceTranscript)
            .filter(VoiceTranscript.id == payload.transcript_id, VoiceTranscript.user_id == user.id)
            .first()
        )
        if t is None:
            raise HTTPException(status_code=404, detail="Transcript not found")
        transcript_text = (t.transcript or "")[:2000]

    msg = TeamMessage(
        user_id=user.id,
        author_name=user.name or user.email.split("@")[0],
        author_role="field"
        if (user.role or "") == "field" or payload.kind == "field_update"
        else "sales",
        kind=payload.kind,
        body=payload.body.strip() or transcript_text,
        transcript_id=payload.transcript_id,
        meta={
            **(payload.meta or {}),
            **({"transcript": transcript_text} if transcript_text else {}),
        },
        status=initial,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _out(msg)


@router.patch("/messages/{message_id}")
def edit_message(
    message_id: int,
    payload: TeamMessageUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = db.get(TeamMessage, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if not _can_manage(msg, user):
        raise HTTPException(status_code=403, detail="You can only edit your own message")
    if msg.status == "sent":
        raise HTTPException(status_code=409, detail="Sent messages cannot be edited")
    msg.body = payload.body.strip()
    if payload.meta is not None:
        msg.meta = payload.meta
    db.commit()
    db.refresh(msg)
    return _out(msg)


@router.post("/messages/{message_id}/review")
def review_message(
    message_id: int,
    payload: ReviewIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = db.get(TeamMessage, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if (user.role or "") == "field" and not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Field executives cannot approve updates")
    if msg.status != "pending":
        raise HTTPException(status_code=409, detail=f"Already reviewed ({msg.status})")
    msg.status = payload.decision
    msg.reviewed_by = user.name or user.email
    msg.reviewed_at = datetime.utcnow()
    db.commit()
    return _out(msg)


@router.post("/messages/{message_id}/send")
def send_message(
    message_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    msg = db.get(TeamMessage, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if not _can_manage(msg, user):
        raise HTTPException(status_code=403, detail="You can only send your own message")
    if msg.status != "approved":
        raise HTTPException(status_code=409, detail="Only approved updates can be sent")
    msg.status = "sent"
    msg.meta = {**(msg.meta or {}), "sent_at": datetime.utcnow().isoformat()}
    db.commit()
    db.refresh(msg)
    return _out(msg)


@router.get("/notifications")
def notifications(
    since_id: int = 0,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reviewed = (
        db.query(TeamMessage)
        .filter(TeamMessage.status.in_(("approved", "rejected", "sent")), TeamMessage.id > since_id)
        .order_by(TeamMessage.id.desc())
        .limit(limit)
        .all()
    )
    own_reviewed = [m for m in reviewed if m.user_id == user.id]
    approved_team = [m for m in reviewed if m.status in ("approved", "sent")]
    pending = db.query(TeamMessage).filter(TeamMessage.status == "pending").count()
    return {
        "pending_approvals": pending,
        "own_reviewed": [_out(m) for m in own_reviewed],
        "approved_updates": [_out(m) for m in approved_team],
        "new_since_id": max([m.id for m in reviewed], default=since_id),
        "unread_estimate": len([m for m in reviewed if m.id > since_id]),
    }


@router.get("/activity")
def activity(
    days: int = Query(default=7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(func.date(TeamMessage.created_at), func.count(TeamMessage.id))
        .group_by(func.date(TeamMessage.created_at))
        .order_by(func.date(TeamMessage.created_at).desc())
        .limit(days)
        .all()
    )
    by_user = (
        db.query(TeamMessage.user_id, TeamMessage.author_name, func.count(TeamMessage.id))
        .group_by(TeamMessage.user_id, TeamMessage.author_name)
        .order_by(func.count(TeamMessage.id).desc())
        .limit(30)
        .all()
    )
    by_status = {
        status: count
        for status, count in db.query(TeamMessage.status, func.count(TeamMessage.id))
        .group_by(TeamMessage.status)
        .all()
    }
    by_kind = {
        kind: count
        for kind, count in db.query(TeamMessage.kind, func.count(TeamMessage.id))
        .group_by(TeamMessage.kind)
        .all()
    }
    return {
        "days": [{"date": str(day), "messages": int(count)} for day, count in rows],
        "by_user": [
            {"user_id": uid, "name": name or f"User {uid}", "messages": int(count)}
            for uid, name, count in by_user
        ],
        "by_status": by_status,
        "by_kind": by_kind,
        "pending_approvals": by_status.get("pending", 0),
    }


@router.get("/rate-today")
def rate_today(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(TeamMessage)
        .filter(TeamMessage.kind == "rate_review")
        .order_by(TeamMessage.id.desc())
        .limit(5)
        .all()
    )
    return {"recent_rate_reviews": [_out(m) for m in rows], "count": len(rows)}
