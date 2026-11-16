"""Kalika-branded outreach template library (5 HTML emails + 19 WhatsApp texts).

The library is generated from ``docs/kalika_gmail_html_templates.zip`` and
``docs/Kalika_WhatsApp_Messages.xlsx`` and shipped as JSON so the production
image stays self-contained (the ``docs/`` folder is not deployed).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_LIBRARY_PATH = Path(__file__).with_name("data") / "kalika_templates.json"

CATEGORIES = ["Products", "ERP", "Automation", "Sales", "Customer Feedback", "Instagram"]


@lru_cache(maxsize=1)
def kalika_library() -> dict[str, Any]:
    try:
        return json.loads(_LIBRARY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 0, "categories": CATEGORIES, "email": [], "whatsapp": []}


def kalika_template_items() -> list[dict[str, Any]]:
    library = kalika_library()
    items: list[dict[str, Any]] = []
    for channel in ("email", "whatsapp"):
        for item in library.get(channel, []):
            items.append(
                {
                    "name": str(item.get("name") or "Untitled")[:128],
                    "channel": channel,
                    "category": str(item.get("category") or "")[:128],
                    "subject": str(item.get("subject") or "")[:255],
                    "body": str(item.get("body") or ""),
                    "strategy": str(item.get("strategy") or "cold_outreach")[:32],
                    "funnel_stage": str(item.get("funnel_stage") or "awareness")[:32],
                }
            )
    return items


def kalika_library_meta() -> dict[str, Any]:
    library = kalika_library()
    return {
        "version": library.get("version", 0),
        "categories": library.get("categories", CATEGORIES),
        "email": len(library.get("email", [])),
        "whatsapp": len(library.get("whatsapp", [])),
    }
