"""Shared contact-field normalization for outreach validation."""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9](?:[A-Z0-9.\-]*[A-Z0-9])?\.[A-Z]{2,}$", re.IGNORECASE)
_INVISIBLE_RE = re.compile(r"[\u0000-\u001f\u007f-\u009f\u00ad\u200b\u200c\u200d\u2060\ufeff]")
_SPLIT_RE = re.compile(r"[\s,;|]+")
_TRIM_RE = re.compile(r"^[\s<>()\[\]{}\"',;:]+|[\s<>()\[\]{}\"',;:]+$")


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return _INVISIBLE_RE.sub("", str(value)).strip()


def normalize_email(value: object) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""
    for candidate in _SPLIT_RE.split(text):
        candidate = _TRIM_RE.sub("", candidate)
        if _EMAIL_RE.fullmatch(candidate):
            return candidate
    fallback = _TRIM_RE.sub("", text)
    return fallback if "@" in fallback else ""


def valid_email(value: object) -> bool:
    candidate = normalize_email(value)
    return bool(candidate) and bool(_EMAIL_RE.fullmatch(candidate))


def normalize_phone(value: object) -> str:
    return re.sub(r"\D", "", clean_text(value))


def valid_phone(value: object) -> bool:
    return len(normalize_phone(value)) >= 8
