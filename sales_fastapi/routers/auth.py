from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
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
    if user is None and "@" not in username:
        # Allow an explicit display-name login alias (for example
        # "Kalika-user1" -> kalikaenterprises@gmail.com). Only use this
        # fallback when no local e-mail account matches, and require the
        # alias to resolve to exactly one account.
        matches = db.query(User).filter(func.lower(User.name) == username).limit(2).all()
        if len(matches) == 1:
            user = matches[0]
            email_address = user.email
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


@router.get("/setup/test")
def test_endpoint():
    """Test endpoint to verify auth router is working."""
    return {"status": "ok", "message": "Auth router is working"}


@router.post("/setup/set-user-password")
def set_user_password(
    email: str,
    password: str,
    db: Session = Depends(get_db),
):
    """Set password for a specific user (for setup purposes)."""
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User not found: {email}")
        
        from .security import hash_password
        user.password_hash = hash_password(password)
        db.commit()
        
        return {"ok": True, "email": email, "message": "Password updated", "user_id": user.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to set password: {str(e)}")


@router.get("/setup/list-users")
def list_users(db: Session = Depends(get_db)):
    """List users in database (for debugging)."""
    users = db.query(User).all()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "has_password": bool(u.password_hash),
            }
            for u in users
        ]
    }


@router.get("/setup/count-users")
def count_users(db: Session = Depends(get_db)):
    """Count users in database."""
    count = db.query(User).count()
    return {"user_count": count}


@router.get("/setup/seed-users")
def seed_initial_users(
    request: Request,
    db: Session = Depends(get_db),
):
    """One-time setup endpoint to create initial users. Only works if no users exist yet."""
    try:
        # Security check: only allow if database is empty or has only the demo user
        existing_users = db.query(User).count()
        if existing_users > 1:
            raise HTTPException(status_code=400, detail="Database already has users. Seed already run.")
        
        from .security import hash_password
        
        created_users = []
        for username, display, pwd, role in (
            ("kalika", "Kalika Admin", "kalika123", "admin"),
            ("field", "Field Executive", "field123", "field"),
        ):
            email_address = f"{username}@kalika.local"
            kuser = db.query(User).filter(User.email == email_address).first()
            if kuser is None:
                kuser = User(
                    google_sub=f"pwd-{username}",
                    email=email_address,
                    name=display,
                    domain="kalika.local",
                    role=role,
                    password_hash=hash_password(pwd),
                )
                db.add(kuser)
                created_users.append(username)
            else:
                # Update password if user already exists
                kuser.password_hash = hash_password(pwd)
                kuser.role = role
                created_users.append(f"{username} (updated)")
        
        db.commit()
        
        log_event(
            db,
            action="auth.seed_users",
            actor_user_id=0,
            resource_type="user",
            resource_id="",
            ip_address=request.client.host if request.client else "",
            detail={"created_users": created_users},
        )
        db.commit()
        
        return {"ok": True, "users_created": created_users}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")
