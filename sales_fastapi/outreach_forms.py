"""Editable customer form links and public feedback/review submissions."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from .config import settings
from .contact_validation import clean_text
from .models import Feedback, IntegrationSetting, User

FORM_LINKS_KEY = "outreach_form_links"
_CONTEXT_KEYS = (
    "contact_name",
    "company",
    "email",
    "phone",
    "order_number",
    "product_name",
)


def default_links() -> dict[str, str]:
    base = settings.OUTREACH_FORM_BASE_URL.strip().rstrip("/")
    return {
        "feedback_url": f"{base}/static/forms/feedback.html",
        "review_url": f"{base}/static/forms/review.html",
        "meeting_url": settings.OUTREACH_MEETING_URL,
    }


def _allowed_url(value: str) -> bool:
    return value.lower().startswith(("http://", "https://", "mailto:"))


def get_form_links(db: Session) -> dict[str, str]:
    defaults = default_links()
    row = db.query(IntegrationSetting).filter(IntegrationSetting.key == FORM_LINKS_KEY).first()
    if row is None or not row.value:
        return {**defaults, "source": "default"}
    try:
        saved = json.loads(row.value)
    except (TypeError, ValueError):
        return {**defaults, "source": "default"}
    if not isinstance(saved, dict):
        return {**defaults, "source": "default"}
    links = dict(defaults)
    for key in defaults:
        value = clean_text(saved.get(key))
        if value and _allowed_url(value):
            links[key] = value
    return {**links, "source": "custom"}


def save_form_links(db: Session, values: dict[str, Any]) -> dict[str, str]:
    links = get_form_links(db)
    saved = {key: links[key] for key in default_links()}
    for key in saved:
        if values.get(key) is not None:
            candidate = clean_text(values[key])
            if not candidate or not _allowed_url(candidate):
                raise ValueError(f"Invalid {key}")
            saved[key] = candidate
    row = db.query(IntegrationSetting).filter(IntegrationSetting.key == FORM_LINKS_KEY).first()
    if row is None:
        row = IntegrationSetting(key=FORM_LINKS_KEY, value="")
        db.add(row)
    row.value = json.dumps(saved)
    db.commit()
    return {**saved, "source": "custom"}


def with_contact_context(url: str, context: dict[str, Any]) -> str:
    cleaned = clean_text(url)
    if not cleaned.lower().startswith(("http://", "https://")):
        return cleaned
    parts = urlsplit(cleaned)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key in _CONTEXT_KEYS:
        value = clean_text(context.get(key))
        if value:
            query.setdefault(key, value[:120])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _owner_user_id(db: Session) -> int:
    user = db.query(User).filter(User.role == "admin").order_by(User.id.asc()).first()
    if user is None:
        user = db.query(User).order_by(User.id.asc()).first()
    return int(user.id) if user is not None else 0


def submit_customer_form(db: Session, category: str, fields: dict[str, Any]) -> Feedback:
    details = [
        f"Name: {clean_text(fields.get('name')) or '-'}",
        f"Email: {clean_text(fields.get('email')) or '-'}",
        f"Phone: {clean_text(fields.get('phone')) or '-'}",
        f"Company: {clean_text(fields.get('company')) or '-'}",
    ]
    for key, title in (
        ("order_number", "Order"),
        ("product_name", "Product"),
        ("title", "Title"),
    ):
        value = clean_text(fields.get(key))
        if value:
            details.append(f"{title}: {value}")
    details.append("")
    details.append(clean_text(fields.get("message")))
    entry = Feedback(
        user_id=_owner_user_id(db),
        category=category,
        rating=int(fields.get("rating") or 5),
        message="\n".join(details)[:8000],
        page="outreach_customer_form",
        status="new",
        notified=False,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
