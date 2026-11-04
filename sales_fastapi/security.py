"""Authentication & secret handling.

- Google Sign-In: verify the Google Identity Services ID token, then issue our
  own short-lived JWT session token.
- Passwords for IMAP/SMTP are encrypted at rest with Fernet (key derived from
  SECRET_KEY) and never returned through the API.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User


# --------------------------------------------------------------------------
# Password / secret encryption
# --------------------------------------------------------------------------
def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:  # pragma: no cover - optional dependency
        return None
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    f = _fernet()
    if f is None:
        return "b64:" + base64.b64encode(plain.encode()).decode()
    return "fernet:" + f.encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    if token.startswith("b64:"):
        return base64.b64decode(token[4:]).decode()
    if token.startswith("fernet:"):
        f = _fernet()
        if f is None:
            return ""
        return f.decrypt(token[7:].encode()).decode()
    return ""


# --------------------------------------------------------------------------
# Username / password (PBKDF2 — no extra dependency)
# --------------------------------------------------------------------------
_PBKDF2_ITERATIONS = 120_000


def hash_password(plain: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, hex_digest = stored.split("$")
        if scheme != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), int(iterations))
        return secrets.compare_digest(digest.hex(), hex_digest)
    except (ValueError, AttributeError):
        return False


# --------------------------------------------------------------------------
# JWT session tokens
# --------------------------------------------------------------------------
def create_access_token(user: User) -> tuple[str, int]:
    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, int(expires.total_seconds())


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# --------------------------------------------------------------------------
# Google ID token verification
# --------------------------------------------------------------------------
def create_oauth_state(user_id: int, purpose: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "purpose": purpose,
            "nonce": secrets.token_urlsafe(18),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_oauth_state(token: str, purpose: str) -> int:
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state") from exc
    if claims.get("purpose") != purpose:
        raise HTTPException(status_code=400, detail="Invalid OAuth state purpose")
    try:
        return int(claims["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid OAuth state subject") from exc


def verify_google_id_token(token: str) -> dict:
    """Return the Google profile claims for a valid ID token.

    In AUTH_DEV_MODE, a synthetic token of the form ``dev:<email>`` is accepted
    so the app can be exercised locally without a Google client.
    """
    if settings.AUTH_DEV_MODE and token.startswith("dev:"):
        email = token[4:].strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="dev token needs an email")
        allowed = settings.auth_dev_allowed_list
        if allowed and email not in allowed:
            raise HTTPException(
                status_code=403,
                detail="dev sign-in is restricted to approved emails",
            )
        return {
            "sub": f"dev-{email}",
            "email": email,
            "name": email.split("@")[0].title(),
            "picture": "",
            "email_verified": True,
        }

    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_CLIENT_ID is not configured on the server",
        )

    try:
        claims = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {exc}") from exc

    # Normalise the verified email before any authorisation decision. The email
    # is taken only from the verified ID token claims, never from the client.
    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Google token has no email claim")
    claims["email"] = email

    if not claims.get("email_verified", False):
        raise HTTPException(status_code=403, detail="Google email is not verified")

    # Strict per-email allowlist (takes precedence over the domain check).
    allowed_emails = settings.google_allowed_emails
    if allowed_emails:
        if email not in allowed_emails:
            raise HTTPException(
                status_code=403,
                detail="This Google account is not authorized for this workspace",
            )
        return claims

    allowed = [d.strip().lower() for d in settings.GOOGLE_ALLOWED_DOMAINS.split(",") if d.strip()]
    if allowed:
        email_domain = email.split("@")[-1].lower()
        if email_domain not in allowed:
            raise HTTPException(status_code=403, detail="Email domain not allowed")
    return claims


# --------------------------------------------------------------------------
# FastAPI dependencies
# --------------------------------------------------------------------------
def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_access_token(authorization.split(" ", 1)[1])
    try:
        user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid session subject") from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Admin-only access (report upload, sync triggers, integration settings).

    Admins are configured via ADMIN_EMAILS; the default is the Kalika operations
    account (ai.solutions@kalisoftai.in). Non-admin users keep read-only dashboards.
    """
    email = (user.email or "").strip().lower()
    if email not in settings.admin_emails and (user.role or "").lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for this action",
        )
    return user


def is_admin_user(user: User) -> bool:
    email = (user.email or "").strip().lower()
    return email in settings.admin_emails or (user.role or "").lower() == "admin"


def require_roles(*roles: str):
    allowed = {role.lower() for role in roles}

    def dependency(user: User = Depends(get_current_user)) -> User:
        if is_admin_user(user):
            return user
        if (user.role or "sales").lower() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role access required: {', '.join(sorted(allowed))}",
            )
        return user

    return dependency
