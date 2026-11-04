"""Template rendering helpers.

Templates use ``{{placeholder}}`` tokens. Unknown placeholders are left intact so
reviewers can spot missing data instead of silently sending blanks.
"""

from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def variables_used(text: str) -> list[str]:
    seen: list[str] = []
    for match in _PLACEHOLDER.findall(text or ""):
        if match not in seen:
            seen.append(match)
    return seen


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


def contact_context(contact: Any, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    context = {
        "name": getattr(contact, "name", "") or "",
        "company": getattr(contact, "company", "") or "",
        "email": getattr(contact, "email", "") or "",
        "phone": getattr(contact, "phone", "") or "",
        "intent": getattr(contact, "intent", "") or "",
        "domain": getattr(contact, "domain", "") or "",
        "context": getattr(contact, "context", "") or "",
    }
    if extra:
        context.update(extra)
    return context
