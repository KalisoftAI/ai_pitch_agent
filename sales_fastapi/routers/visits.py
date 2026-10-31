"""Company visit history with GCS photo/video attachments and field activity."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import CompanyVisit, Contact, TeamMessage, User, VoiceTranscript
from ..security import get_current_user, is_admin_user
from ..services import GCSStorage

router = APIRouter(prefix="/visits", tags=["visits"])
MAX_MEDIA_BYTES = 100 * 1024 * 1024


class VisitIn(BaseModel):
    company: str = Field(..., min_length=2, max_length=255)
    contact_id: int = 0
    contact_name: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=64)
    visit_date: str = Field(default="", max_length=10)
    visit_type: str = Field(default="in_person", max_length=32)
    sales_person: str = Field(default="", max_length=255)
    purpose: str = Field(default="", max_length=512)
    notes: str = Field(default="", max_length=20_000)
    outcome: str = Field(default="", max_length=64)
    next_action: str = Field(default="", max_length=5_000)
    follow_up_date: str = Field(default="", max_length=10)
    status: str = Field(default="completed", max_length=32)


class VisitUpdate(BaseModel):
    company: str | None = Field(default=None, max_length=255)
    contact_id: int | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=64)
    visit_date: str | None = Field(default=None, max_length=10)
    visit_type: str | None = Field(default=None, max_length=32)
    sales_person: str | None = Field(default=None, max_length=255)
    purpose: str | None = Field(default=None, max_length=512)
    notes: str | None = Field(default=None, max_length=20_000)
    outcome: str | None = Field(default=None, max_length=64)
    next_action: str | None = Field(default=None, max_length=5_000)
    follow_up_date: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None, max_length=32)


def _out(visit: CompanyVisit) -> dict:
    return {
        "id": visit.id,
        "user_id": visit.user_id,
        "contact_id": visit.contact_id,
        "company": visit.company,
        "contact_name": visit.contact_name,
        "contact_phone": visit.contact_phone,
        "visit_date": visit.visit_date,
        "visit_type": visit.visit_type,
        "sales_person": visit.sales_person,
        "purpose": visit.purpose,
        "notes": visit.notes,
        "outcome": visit.outcome,
        "next_action": visit.next_action,
        "follow_up_date": visit.follow_up_date,
        "status": visit.status,
        "media": visit.media or [],
        "created_at": str(visit.created_at),
        "updated_at": str(visit.updated_at),
    }


def _owned(db: Session, visit_id: int, user: User) -> CompanyVisit:
    visit = db.get(CompanyVisit, visit_id)
    if visit is None or (visit.user_id != user.id and not is_admin_user(user)):
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


@router.get("/stats")
def visit_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    base = db.query(CompanyVisit).filter(CompanyVisit.user_id == user.id)
    by_outcome = {
        outcome or "unspecified": int(count)
        for outcome, count in base.with_entities(CompanyVisit.outcome, func.count(CompanyVisit.id))
        .group_by(CompanyVisit.outcome)
        .all()
    }
    by_type = {
        kind: int(count)
        for kind, count in base.with_entities(CompanyVisit.visit_type, func.count(CompanyVisit.id))
        .group_by(CompanyVisit.visit_type)
        .all()
    }
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "visits": base.count(),
        "companies": base.with_entities(func.count(func.distinct(CompanyVisit.company))).scalar()
        or 0,
        "media": sum(len(v.media or []) for v in base.all()),
        "by_outcome": by_outcome,
        "by_type": by_type,
        "this_month": base.filter(CompanyVisit.visit_date.like(f"{today[:7]}%")).count(),
        "pending_followups": base.filter(
            CompanyVisit.follow_up_date >= today, CompanyVisit.status != "closed"
        ).count(),
    }


@router.get("/activity")
def field_activity(
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc).date().toordinal() - days + 1
    visits = db.query(CompanyVisit).filter(CompanyVisit.user_id == user.id).all()
    recent = []
    for visit in visits:
        try:
            if datetime.fromisoformat(visit.visit_date).date().toordinal() < since:
                continue
        except ValueError:
            pass
        recent.append(visit)
    by_day: dict[str, int] = {}
    by_person: dict[str, int] = {}
    for visit in recent:
        by_day[visit.visit_date or "unknown"] = by_day.get(visit.visit_date or "unknown", 0) + 1
        by_person[visit.sales_person or "unassigned"] = (
            by_person.get(visit.sales_person or "unassigned", 0) + 1
        )
    voice = db.query(VoiceTranscript).filter(VoiceTranscript.user_id == user.id).count()
    messages = db.query(TeamMessage).filter(TeamMessage.user_id == user.id).count()
    approved = (
        db.query(TeamMessage)
        .filter(TeamMessage.user_id == user.id, TeamMessage.status.in_(("approved", "sent")))
        .count()
    )
    return {
        "days": days,
        "visits": len(recent),
        "voice_transcripts": voice,
        "messages": messages,
        "approved_updates": approved,
        "by_day": [{"date": day, "visits": count} for day, count in sorted(by_day.items())],
        "by_sales_person": [
            {"name": name, "visits": count}
            for name, count in sorted(by_person.items(), key=lambda item: -item[1])
        ],
    }


@router.get("")
def list_visits(
    company: str = "",
    outcome: str = "",
    status: str = "",
    limit: int = Query(default=100, ge=1, le=500),
    all_users: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CompanyVisit)
    if not (all_users and is_admin_user(user)):
        query = query.filter(CompanyVisit.user_id == user.id)
    if company:
        query = query.filter(CompanyVisit.company.ilike(f"%{company}%"))
    if outcome:
        query = query.filter(CompanyVisit.outcome == outcome)
    if status:
        query = query.filter(CompanyVisit.status == status)
    rows = query.order_by(CompanyVisit.visit_date.desc(), CompanyVisit.id.desc()).limit(limit).all()
    return [_out(visit) for visit in rows]


@router.post("", status_code=201)
def create_visit(
    payload: VisitIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    data = payload.model_dump()
    data["visit_date"] = payload.visit_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if payload.contact_id:
        contact = (
            db.query(Contact)
            .filter(Contact.id == payload.contact_id, Contact.user_id == user.id)
            .first()
        )
        if contact is None:
            raise HTTPException(status_code=404, detail="Contact not found")
        data["company"] = data["company"] or contact.company
        data["contact_name"] = data["contact_name"] or contact.name
        data["contact_phone"] = data["contact_phone"] or contact.phone
    data["sales_person"] = payload.sales_person or user.name or user.email
    visit = CompanyVisit(user_id=user.id, **data)
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return _out(visit)


@router.get("/{visit_id}")
def get_visit(visit_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(_owned(db, visit_id, user))


@router.patch("/{visit_id}")
def update_visit(
    visit_id: int,
    payload: VisitUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = _owned(db, visit_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(visit, field, value)
    visit.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(visit)
    return _out(visit)


@router.delete("/{visit_id}", status_code=204)
def delete_visit(
    visit_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    visit = _owned(db, visit_id, user)
    db.delete(visit)
    db.commit()


@router.post("/{visit_id}/media", status_code=201)
async def upload_media(
    visit_id: int,
    file: UploadFile = File(...),
    kind: str = Form(default="photo"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = _owned(db, visit_id, user)
    if not file.filename:
        raise HTTPException(status_code=400, detail="A photo or video file is required")
    content_type = file.content_type or "application/octet-stream"
    if not (content_type.startswith("image/") or content_type.startswith("video/")):
        raise HTTPException(status_code=400, detail="Only image or video attachments are supported")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > MAX_MEDIA_BYTES:
        raise HTTPException(status_code=413, detail="Attachment exceeds the 100 MB limit")
    suffix = Path(file.filename).suffix.lower()
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(file.filename).stem)[:80] or "media"
    blob_name = f"{settings.GCS_PATH_VISITS}users/{user.id}/{visit.id}/{int(time.time())}-{safe_name}{suffix}"
    gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_MEDIA)
    if not gcs.available:
        raise HTTPException(
            status_code=503, detail="GCS media storage is not configured; set ADC credentials"
        )
    if not gcs.upload_bytes(blob_name, data, content_type):
        raise HTTPException(status_code=502, detail="Attachment upload to GCS failed")
    item = {
        "kind": kind,
        "name": file.filename,
        "gcs_path": blob_name,
        "content_type": content_type,
        "size_bytes": len(data),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    visit.media = [*(visit.media or []), item]
    db.commit()
    db.refresh(visit)
    return item
