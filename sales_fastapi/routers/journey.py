"""Customer journey collection endpoints: events, behaviours, stories, patterns."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..customer_journey import (
    PATTERNS, STAGES, behaviours, journey_summary, record_event, stories,
)
from ..database import get_db
from ..models import User
from ..security import get_current_user

router = APIRouter(prefix="/journey", tags=["journey"])


class JourneyEventIn(BaseModel):
    contact_id: int = Field(..., ge=1)
    customer_type: str = Field(default="lead")
    stage: str
    event: str = Field(..., min_length=2, max_length=64)
    channel: str = ""
    detail: str = ""
    meta: dict = Field(default_factory=dict)


@router.get("/patterns")
def patterns(user: User = Depends(get_current_user)):
    return {"stages": STAGES, "patterns": PATTERNS}


@router.post("/event")
def add_event(payload: JourneyEventIn, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    row = record_event(db, user_id=user.id, contact_id=payload.contact_id,
                       customer_type=payload.customer_type, stage=payload.stage,
                       event=payload.event, channel=payload.channel, detail=payload.detail,
                       meta=payload.meta)
    return {"id": row.id, "stage": row.stage, "event": row.event, "created_at": str(row.created_at)}


@router.get("/behaviours")
def get_behaviours(days: int = Query(default=30, ge=1, le=365),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return behaviours(db, user.id, days=days)


@router.get("/stories")
def get_stories(limit: int = Query(default=20, ge=1, le=100),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return stories(db, user.id, limit=limit)


@router.get("/summary")
def get_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return journey_summary(db, user.id)
