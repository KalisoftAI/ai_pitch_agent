"""User management and role assignment (admin only)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..models import (
    Campaign,
    CompanyVisit,
    Contact,
    TeamMessage,
    User,
    VoiceTranscript,
)
from ..schemas import UserOut
from ..security import hash_password, is_admin_user, require_admin

router = APIRouter(prefix="/users", tags=["users"])

Role = Literal["admin", "sales", "field"]


class UserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    name: str = Field(default="", max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: Role = "sales"


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


def _normalize_email(value: str) -> str:
    email_address = value.strip().lower()
    if "@" not in email_address:
        email_address = f"{email_address}@kalika.local"
    return email_address


def _out(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role or "sales",
        "is_active": user.is_active,
        "domain": user.domain,
        "created_at": str(user.created_at),
        "last_login_at": str(user.last_login_at) if user.last_login_at else None,
        "admin_by_email": is_admin_user(user),
        "password_set": bool(user.password_hash),
    }


@router.get("", response_model=list[UserOut])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id.asc()).all()


@router.get("/detail")
def list_users_detail(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [_out(user) for user in db.query(User).order_by(User.id.asc()).all()]


@router.get("/roles")
def roles(admin: User = Depends(require_admin)):
    return {
        "roles": [
            {
                "name": "admin",
                "description": "Full workspace access, syncs, exports, user management.",
            },
            {
                "name": "sales",
                "description": "Dashboard, catalogue approval, team review, reports.",
            },
            {"name": "field", "description": "Field updates, visits, voice capture; no approvals."},
        ],
    }


@router.post("", status_code=201)
def create_user(
    payload: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    email_address = _normalize_email(payload.email)
    if db.query(User).filter(User.email == email_address).first():
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    user = User(
        google_sub=f"local:{email_address}",
        email=email_address,
        name=payload.name.strip() or email_address.split("@")[0].title(),
        domain=email_address.split("@")[-1].lower(),
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_event(
        db,
        action="users.create",
        actor_user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        status="success",
        detail={"email": email_address, "role": payload.role},
    )
    db.commit()
    return _out(user)


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and changes.get("is_active") is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if user.id == admin.id and changes.get("role") and changes["role"] != "admin":
        raise HTTPException(status_code=400, detail="You cannot remove your own admin role")
    if changes.get("role") and user.role == "admin" and changes["role"] != "admin":
        remaining = db.query(User).filter(User.id != user.id, User.is_active.is_(True)).all()
        admin_emails = settings.admin_emails
        other_admins = [
            row for row in remaining if row.role == "admin" or row.email.lower() in admin_emails
        ]
        if not other_admins:
            raise HTTPException(status_code=400, detail="At least one admin is required")
    if "password" in changes:
        user.password_hash = hash_password(changes.pop("password"))
    for field, value in changes.items():
        if value is not None:
            setattr(user, field, value)
    db.commit()
    db.refresh(user)
    log_event(
        db,
        action="users.update",
        actor_user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        status="success",
        detail={"fields": sorted(changes.keys())},
    )
    db.commit()
    return _out(user)


@router.get("/activity")
def user_activity(
    days: int = 30, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(days=max(1, min(days, 365)))
    users = db.query(User).order_by(User.id.asc()).all()
    contacts = dict(
        db.query(Contact.user_id, func.count(Contact.id)).group_by(Contact.user_id).all()
    )
    visits = dict(
        db.query(CompanyVisit.user_id, func.count(CompanyVisit.id))
        .group_by(CompanyVisit.user_id)
        .all()
    )
    voice = dict(
        db.query(VoiceTranscript.user_id, func.count(VoiceTranscript.id))
        .group_by(VoiceTranscript.user_id)
        .all()
    )
    messages = dict(
        db.query(TeamMessage.user_id, func.count(TeamMessage.id))
        .group_by(TeamMessage.user_id)
        .all()
    )
    campaigns = dict(
        db.query(Campaign.user_id, func.count(Campaign.id)).group_by(Campaign.user_id).all()
    )
    recent_logins = dict(db.query(User.id, User.last_login_at).all())
    return {
        "days": days,
        "since": str(since),
        "users": [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "last_login_at": str(recent_logins.get(user.id))
                if recent_logins.get(user.id)
                else None,
                "contacts": int(contacts.get(user.id, 0)),
                "visits": int(visits.get(user.id, 0)),
                "voice": int(voice.get(user.id, 0)),
                "messages": int(messages.get(user.id, 0)),
                "campaigns": int(campaigns.get(user.id, 0)),
            }
            for user in users
        ],
    }


@router.get("/{user_id}")
def get_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _out(user)
