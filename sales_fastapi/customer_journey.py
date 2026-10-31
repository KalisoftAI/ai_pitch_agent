"""Customer journey collection + behaviour patterns.

Patterns are opinionated playbooks per customer type. Every interaction
(template preview/queue, feedback, reply, order, complaint) can be recorded as
a JourneyEvent; stories aggregate the latest events into readable timelines.

Stdlib + SQLAlchemy only; no LLM calls here (the llm layer consumes these).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import JourneyEvent

# Journey stages (funnel) in order.
STAGES = ["awareness", "interest", "evaluation", "purchase", "onboarding", "retention", "advocacy"]

# Behaviour patterns per customer type: stage -> expected events + next best action.
PATTERNS: dict[str, dict] = {
    "new_customer": {
        "label": "New customer",
        "detect": "contact synced in last 7 days, no order yet",
        "stages": {
            "awareness": ["welcome_message", "catalogue_shared"],
            "interest": ["rate_shared", "requirement_captured"],
            "evaluation": ["quotation_sent", "sample_requested"],
            "purchase": ["first_order"],
            "onboarding": ["delivery_confirmed", "feedback_requested"],
            "retention": ["repeat_order"],
            "advocacy": ["referral_or_review"],
        },
        "next_action": {
            "awareness": "WA-NEW-01",
            "interest": "WA-NEW-02",
            "evaluation": "WA-QT-01",
            "onboarding": "WA-FBK-02",
            "retention": "WA-RT-01",
            "advocacy": "WA-EXP-01",
        },
        "feedback_prompt": "Ask what packaging problem they need solved first; then share rates.",
    },
    "repeat_customer": {
        "label": "Repeat customer",
        "detect": "2+ orders in the sales register",
        "stages": {
            "purchase": ["order_placed"],
            "onboarding": ["dispatch_update", "delivery_confirmed"],
            "retention": ["feedback_requested", "reorder_nudge"],
            "advocacy": ["review_collected", "referral_asked"],
        },
        "next_action": {
            "purchase": "WA-ORD-01",
            "onboarding": "WA-DSP-01",
            "retention": "WA-FBK-06",
            "advocacy": "WA-RT-01",
        },
        "feedback_prompt": "Ask for a 1-5 rating plus one improvement idea; keep it under 30 seconds.",
    },
    "at_risk": {
        "label": "At risk",
        "detect": "negative sentiment, complaint, or no order in 60 days",
        "stages": {
            "retention": ["complaint_raised", "ticket_created"],
            "advocacy": ["issue_resolved", "satisfaction_confirmed"],
        },
        "next_action": {"retention": "WA-FBK-06", "advocacy": "WA-FU-03"},
        "feedback_prompt": "Ask what went wrong, acknowledge, then confirm resolution in one message.",
    },
    "high_value": {
        "label": "High value",
        "detect": "top-decile gross value from sales registers",
        "stages": {
            "retention": ["dedicated_followup", "quarterly_review"],
            "advocacy": ["case_study_requested", "referral_asked"],
        },
        "next_action": {"retention": "WA-RT-01", "advocacy": "WA-EXP-01"},
        "feedback_prompt": "Ask for strategic feedback (service, lead time, quality) and offer a review call.",
    },
}


def classify_customer_type(
    *,
    recent_order: bool = False,
    order_count: int = 0,
    gross_value: float = 0.0,
    negative_sentiment: bool = False,
    days_since_order: int | None = None,
) -> str:
    """Deterministic classifier used before any LLM call."""
    if negative_sentiment or (days_since_order is not None and days_since_order > 60):
        return "at_risk"
    if gross_value >= 1_000_000 or order_count >= 10:
        return "high_value"
    if order_count >= 2:
        return "repeat_customer"
    return "new_customer"


def record_event(
    db: Session,
    *,
    user_id: int,
    contact_id: int,
    customer_type: str,
    stage: str,
    event: str,
    channel: str = "",
    detail: str = "",
    meta: dict | None = None,
) -> JourneyEvent:
    if stage not in STAGES:
        raise ValueError(f"unknown stage '{stage}'")
    row = JourneyEvent(
        user_id=user_id,
        contact_id=contact_id,
        customer_type=customer_type,
        stage=stage,
        event=event,
        channel=channel,
        detail=detail[:2000],
        meta=meta or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def behaviours(db: Session, user_id: int, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(JourneyEvent)
        .filter(JourneyEvent.user_id == user_id, JourneyEvent.created_at >= since)
        .all()
    )
    by_stage: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    by_event: dict[str, int] = {}
    for r in rows:
        by_stage[r.stage] = by_stage.get(r.stage, 0) + 1
        by_type[r.customer_type] = by_type.get(r.customer_type, 0) + 1
        by_channel[r.channel or "unknown"] = by_channel.get(r.channel or "unknown", 0) + 1
        by_event[r.event] = by_event.get(r.event, 0) + 1
    return {
        "days": days,
        "total": len(rows),
        "by_stage": by_stage,
        "by_customer_type": by_type,
        "by_channel": by_channel,
        "top_events": sorted(by_event.items(), key=lambda x: -x[1])[:10],
    }


def stories(db: Session, user_id: int, limit: int = 20) -> list[dict]:
    """Group latest events per contact into readable customer stories."""
    rows = (
        db.query(JourneyEvent)
        .filter(JourneyEvent.user_id == user_id)
        .order_by(JourneyEvent.id.desc())
        .limit(500)
        .all()
    )
    grouped: dict[int, list[JourneyEvent]] = {}
    for r in rows:
        grouped.setdefault(r.contact_id, []).append(r)
    out = []
    for contact_id, events in list(grouped.items())[:limit]:
        events_sorted = sorted(events, key=lambda e: e.id)
        latest = events_sorted[-1]
        pattern = PATTERNS.get(latest.customer_type, {})
        out.append(
            {
                "contact_id": contact_id,
                "customer_type": latest.customer_type,
                "customer_type_label": pattern.get("label", latest.customer_type),
                "current_stage": latest.stage,
                "next_action_template": pattern.get("next_action", {}).get(latest.stage, ""),
                "feedback_prompt": pattern.get("feedback_prompt", ""),
                "timeline": [
                    {
                        "stage": e.stage,
                        "event": e.event,
                        "channel": e.channel,
                        "detail": e.detail,
                        "at": str(e.created_at),
                    }
                    for e in events_sorted[-10:]
                ],
            }
        )
    return out


def journey_summary(db: Session, user_id: int) -> dict:
    total = (
        db.query(func.count(JourneyEvent.id)).filter(JourneyEvent.user_id == user_id).scalar() or 0
    )
    contacts = (
        db.query(func.count(func.distinct(JourneyEvent.contact_id)))
        .filter(JourneyEvent.user_id == user_id)
        .scalar()
        or 0
    )
    return {
        "events": int(total),
        "contacts": int(contacts),
        "stages": STAGES,
        "patterns": {
            k: {"label": v["label"], "detect": v["detect"], "stages": list(v["stages"].keys())}
            for k, v in PATTERNS.items()
        },
    }
