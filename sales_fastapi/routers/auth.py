from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..governance.audit import log_event
from ..models import User
from ..schemas import GoogleLoginIn, PasswordLoginIn, SetPasswordIn, TokenOut, UserOut
from ..security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_google_id_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _domain_of(email_address: str) -> str:
    return email_address.split("@")[-1].lower() if "@" in email_address else ""


@router.post("/google", response_model=TokenOut)
def google_login(
    payload: GoogleLoginIn,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenOut:
    try:
        claims = verify_google_id_token(payload.id_token)
    except HTTPException as exc:
        # Audit blocked/failed sign-ins. Never log the token itself.
        log_event(
            db,
            action="auth.login_blocked",
            actor_user_id=0,
            resource_type="user",
            resource_id="",
            status="blocked",
            ip_address=request.client.host if request.client else "",
            detail={"method": "google", "reason": str(exc.detail)[:200]},
        )
        db.commit()
        raise
    email_address = (claims.get("email") or "").strip().lower()

    user = db.query(User).filter(User.email == email_address).first()
    if user is None:
        # Auto-provisioning is only reachable for allowlisted emails: the
        # allowlist check in verify_google_id_token has already rejected every
        # other account. Admin rights come only from explicit RBAC config
        # (ADMIN_EMAILS / users.role), never from the email alone here.
        user = User(
            google_sub=claims.get("sub", email_address),
            email=email_address,
            name=claims.get("name", ""),
            picture=claims.get("picture", ""),
            domain=_domain_of(email_address),
            role="sales",
        )
        db.add(user)
    else:
        if not user.is_active:
            log_event(
                db,
                action="auth.login_blocked",
                actor_user_id=user.id,
                resource_type="user",
                resource_id=str(user.id),
                status="blocked",
                ip_address=request.client.host if request.client else "",
                detail={"method": "google", "reason": "account disabled"},
            )
            db.commit()
            raise HTTPException(status_code=403, detail="Account disabled")
        user.name = claims.get("name", "") or user.name
        user.picture = claims.get("picture", "") or user.picture
        # Link a dev/local placeholder subject to the real Google subject,
        # preserving the existing user id and all related data.
        sub = claims.get("sub", "")
        if sub and user.google_sub.startswith(("dev-", "local:")):
            conflict = db.query(User).filter(User.google_sub == sub, User.id != user.id).first()
            if conflict is None:
                user.google_sub = sub
    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    log_event(
        db,
        action="auth.login",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        tenant_id=user.domain,
        ip_address=request.client.host if request.client else "",
        detail={"email": email_address, "method": "google"},
    )
    db.commit()

    token, expires_in = create_access_token(user)
    return TokenOut(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/password", response_model=TokenOut)
def password_login(
    payload: PasswordLoginIn,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenOut:
    """Kalika username+password sign-in (works alongside Google sign-in)."""
    username = payload.username.strip().lower()
    email_address = username if "@" in username else f"{username}@kalika.local"

    user = db.query(User).filter(User.email == email_address).first()
    if (
        user is None
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    user.last_login_at = datetime.utcnow()
    db.commit()

    log_event(
        db,
        action="auth.login",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        tenant_id=user.domain,
        ip_address=request.client.host if request.client else "",
        detail={"email": email_address, "method": "password"},
    )
    db.commit()

    token, expires_in = create_access_token(user)
    return TokenOut(access_token=token, expires_in=expires_in)


@router.post("/set-password")
def set_password(
    payload: SetPasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set or update the signed-in user's password (enables username+password login)."""
    user.password_hash = hash_password(payload.password)
    db.commit()
    return {"ok": True, "username": user.email.split("@")[0]}
