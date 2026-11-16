"""Template rendering helpers.

Templates use ``{{placeholder}}`` tokens. ``render_resolved`` applies per-field
fallbacks and strips any remaining placeholders so nothing unresolved is ever sent.
``render`` keeps unknown placeholders visible for reviewer spotting (legacy).
"""

from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")

# Fallbacks used when a contact field is missing. Keys are the canonical field name.
_FALLBACKS: dict[str, str] = {
    "name": "there",
    "contact_name": "there",
    "company": "your organization",
    "company_name": "your organization",
    "email": "",
    "phone": "",
    "mobile": "",
    "designation": "Team",
    "intent": "",
    "domain": "",
    "context": "",
    "product_name": "Kalika Enterprises packaging",
    "product": "Kalika Enterprises packaging",
    "product_or_solution": "Kalika Enterprises packaging",
    "order_number": "",
    "order_no": "",
    "order_date": "",
    "review_url": "",
    "review_link": "",
    "feedback_form_url": "",
    "meeting_or_enquiry_url": "",
}

# Aliases -> canonical key (so {{mobile}} resolves from phone, etc.).
_ALIASES: dict[str, str] = {
    "mobile": "phone",
    "mobile_number": "phone",
    "phone_number": "phone",
    "contact": "name",
    "full_name": "name",
    "person": "name",
    "organisation": "company",
    "organization": "company",
    "org": "company",
    "companyname": "company",
    "mail": "email",
    "email_address": "email",
    "role": "designation",
    "title": "designation",
    "position": "designation",
    "voucher_no": "order_number",
    "order_id": "order_number",
    "order_no": "order_number",
    "sale_date": "order_date",
    "product_or_solution": "product_name",
    "solution": "product_name",
    "review_link": "review_url",
    "feedback_url": "feedback_form_url",
    "meeting_url": "meeting_or_enquiry_url",
    "enquiry_url": "meeting_or_enquiry_url",
}


def variables_used(text: str) -> list[str]:
    seen: list[str] = []
    for match in _PLACEHOLDER.findall(text or ""):
        if match not in seen:
            seen.append(match)
    return seen


def _context_value(key: str, context: dict[str, Any]) -> Any:
    """Look a key up case-insensitively (templates use CONTACT_NAME, context uses contact_name)."""
    for probe in (key, key.lower(), key.upper()):
        value = context.get(probe)
        if value not in (None, ""):
            return value
    return None


def _resolve_value(key: str, context: dict[str, Any]) -> str | None:
    """Return a display value for *key* from *context* with aliases+fallbacks, or None."""
    value = _context_value(key, context)
    if value not in (None, ""):
        return str(value)
    alias = _ALIASES.get(key.lower(), _ALIASES.get(key, ""))
    if alias:
        value = _context_value(alias, context)
        if value not in (None, ""):
            return str(value)
    # fallbacks (by key, then by alias target)
    for probe in (key, key.lower(), alias):
        if probe in _FALLBACKS:
            return _FALLBACKS[probe]
    return None


def render(text: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = context.get(key)
        return str(value) if value not in (None, "") else match.group(0)

    return _PLACEHOLDER.sub(replace, text or "")


def render_optional(text: str, context: dict[str, Any]) -> str:
    """Like :func:`render`, but drops placeholders whose value is empty.

    Optional fields such as ``{{company_suffix}}`` disappear instead of leaking
    into the message, while genuinely unknown placeholders stay visible so typos
    are still spotted.
    """

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            return match.group(0)
        value = context.get(key)
        return str(value) if value not in (None, "") else ""

    return _PLACEHOLDER.sub(replace, text or "")


def render_resolved(text: str, context: dict[str, Any]) -> str:
    """Render with fallbacks and strip any remaining ``{{...}}`` tokens.

    Use this for content that will actually be sent or previewed-as-final so that
    no unresolved placeholder ever reaches a recipient.
    """

    def replace(match: re.Match[str]) -> str:
        resolved = _resolve_value(match.group(1), context)
        # resolved is "" for intentionally-blank fallbacks (email/phone/intent);
        # None means truly unknown -> strip to avoid leaking a token.
        return resolved if resolved is not None else ""

    out = _PLACEHOLDER.sub(replace, text or "")
    # belt-and-suspenders: drop any stray tokens that survived
    return _PLACEHOLDER.sub("", out)


def render_resolved_report(text: str, context: dict[str, Any]) -> tuple[str, list[str]]:
    """Like :func:`render_resolved` but also reports placeholders with no source value.

    Fallbacks are still applied (so a message never ships with ``{{...}}`` left in),
    but the caller can flag recipients whose contact/order data was incomplete.
    """
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if _context_value(key, context) in (None, ""):
            alias = _ALIASES.get(key.lower(), _ALIASES.get(key, ""))
            if not alias or _context_value(alias, context) in (None, ""):
                normalized = key.lower()
                if normalized not in missing:
                    missing.append(normalized)
        resolved = _resolve_value(key, context)
        return resolved if resolved is not None else ""

    out = _PLACEHOLDER.sub(replace, text or "")
    return _PLACEHOLDER.sub("", out), missing


def contact_context(contact: Any, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    name_value = (getattr(contact, "name", "") or getattr(contact, "contact_name", "") or "")
    company_value = getattr(contact, "company", "") or ""
    phone_value = getattr(contact, "phone", "") or getattr(contact, "mobile", "") or ""
    designation = (
        getattr(contact, "designation", "")
        or getattr(contact, "purchase_contact_role", "")
        or getattr(contact, "role", "")
        or ""
    )
    context = {
        "name": name_value,
        "contact_name": name_value,
        "company": company_value,
        "company_name": company_value,
        "email": getattr(contact, "email", "") or "",
        "phone": phone_value,
        "mobile": phone_value,
        "designation": designation,
        "intent": getattr(contact, "intent", "") or getattr(contact, "category", "") or "",
        "domain": getattr(contact, "domain", "") or "",
        "context": getattr(contact, "context", "") or getattr(contact, "requirements", "") or "",
        # common defaults so these always resolve
        "product_name": "Kalika Enterprises packaging",
        "product": "Kalika Enterprises packaging",
    }
    if extra:
        context.update(extra)
    return context


_HTML_TAG_RE = re.compile(
    r"<\s*/?\s*(?:br|p|div|span|html|body|head|title|a|img|table|tr|td|th|tbody|thead|ul|ol|li|h[1-6]|strong|b|i|em|u|font|pre|blockquote|center|hr|meta|style|script|link)\b[^>]*>",
    re.IGNORECASE,
)


def looks_html(text: str | None) -> bool:
    """True when the content contains HTML markup (used for channel compatibility)."""
    return bool(_HTML_TAG_RE.search(text or ""))
