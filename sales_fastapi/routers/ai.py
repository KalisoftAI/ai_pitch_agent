"""Data-driven sales recommendations and communication analytics.

This router intentionally separates facts from generation: every recommendation
is derived from live rows in the workspace database (ERP sync, visits, voice,
team reviews and contacts). When no LLM key is configured the response reports
that status instead of inventing prose.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..customer_journey import STAGES, classify_customer_type, journey_summary
from ..database import get_db
from ..erp_sync import dispatch_stats, latest_report_date, orders_stats
from ..models import (
    Campaign,
    CampaignMessage,
    CompanyVisit,
    Contact,
    EmailConnection,
    ErpDispatch,
    ErpOrder,
    Feedback,
    JourneyEvent,
    ProductRate,
    SocialMetric,
    TeamMessage,
    User,
    VoiceTranscript,
    WhatsAppMessage,
)
from ..security import get_current_user, is_admin_user

router = APIRouter(prefix="/ai", tags=["ai"])


def _rec(priority: str, area: str, text: str, action: str, **evidence) -> dict:
    return {
        "priority": priority,
        "area": area,
        "text": text,
        "action": action,
        "evidence": evidence,
    }


def build_recommendations(db: Session, user: User) -> dict:
    day = latest_report_date(db)
    dispatches = dispatch_stats(db, day)
    orders = orders_stats(db, day)
    recs: list[dict] = []
    counts: dict[str, int] = {}

    pending_lines = (
        db.query(ErpDispatch)
        .filter(ErpDispatch.report_date == day, ErpDispatch.status != "Completed")
        .count()
        if day
        else 0
    )
    counts["pending_dispatch_lines"] = pending_lines
    if pending_lines:
        recs.append(
            _rec(
                "high",
                "Dispatch",
                f"{pending_lines} dispatch line(s) are not Completed. Work the plant-wise backlog today.",
                "open_dispatch",
                report_date=day,
                pending_lines=pending_lines,
            )
        )

    completion = dispatches.get("completion_pct", 0) or 0
    counts["completion_pct"] = completion
    if day and completion < 60:
        recs.append(
            _rec(
                "high",
                "Delivery",
                f"Delivery completion is {completion}% (below the 60% floor). Reconfirm schedules with production.",
                "review_delivery",
                report_date=day,
                completion_pct=completion,
            )
        )

    top_orders = (
        (
            db.query(ErpOrder.customer, func.sum(ErpOrder.total_value), func.count(ErpOrder.id))
            .filter(ErpOrder.report_date == day)
            .group_by(ErpOrder.customer)
            .order_by(func.sum(ErpOrder.total_value).desc())
            .limit(5)
            .all()
        )
        if day
        else []
    )
    counts["order_customers"] = (
        db.query(func.count(func.distinct(ErpOrder.customer)))
        .filter(ErpOrder.report_date == day)
        .scalar()
        if day
        else 0
    )
    for customer, value, order_count in top_orders[:3]:
        contact = (
            db.query(Contact)
            .filter(Contact.user_id == user.id, func.lower(Contact.company) == func.lower(customer))
            .first()
        )
        if contact is None:
            recs.append(
                _rec(
                    "medium",
                    "Pipeline",
                    f"Top ERP customer '{customer}' has no workspace contact for this user. Add a buyer contact.",
                    "create_contact",
                    customer=customer,
                    order_value=float(value or 0),
                    orders=int(order_count or 0),
                )
            )

    pending_field = db.query(TeamMessage).filter(TeamMessage.status == "pending").count()
    counts["pending_field_updates"] = pending_field
    if pending_field:
        recs.append(
            _rec(
                "high",
                "Field updates",
                f"{pending_field} field update(s) await review. Approve or reject before the next call.",
                "review_team",
                pending=pending_field,
            )
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    due_followups = (
        db.query(CompanyVisit)
        .filter(
            CompanyVisit.user_id == user.id,
            CompanyVisit.follow_up_date != "",
            CompanyVisit.follow_up_date <= today,
            CompanyVisit.status != "closed",
        )
        .count()
    )
    counts["due_visits"] = due_followups
    if due_followups:
        recs.append(
            _rec(
                "high",
                "Visits",
                f"{due_followups} company visit follow-up(s) are due or overdue.",
                "open_visits",
                due=due_followups,
                today=today,
            )
        )

    pending_rates = (
        db.query(ProductRate)
        .filter(ProductRate.user_id == user.id, ProductRate.status == "pending")
        .count()
    )
    counts["pending_product_rates"] = pending_rates
    if pending_rates:
        recs.append(
            _rec(
                "medium",
                "Pricing",
                f"{pending_rates} product rate(s) are pending approval. Complete the daily rate review.",
                "review_rates",
                pending=pending_rates,
            )
        )

    voice_leads = 0
    voice_rows = (
        db.query(VoiceTranscript)
        .filter(
            VoiceTranscript.user_id == user.id,
            VoiceTranscript.status.in_(("done", "done_heuristic")),
        )
        .order_by(VoiceTranscript.id.desc())
        .limit(100)
        .all()
    )
    for row in voice_rows:
        if (row.lead or {}).get("intent") in ("order", "rate", "sample"):
            voice_leads += 1
    counts["voice_leads"] = voice_leads
    if voice_leads:
        recs.append(
            _rec(
                "medium",
                "Voice",
                f"{voice_leads} analysed call(s) contain ordering/rate intent. Provision them as contacts and follow up.",
                "open_voice",
                leads=voice_leads,
            )
        )

    recent_cutoff = datetime.utcnow() - timedelta(days=7)
    recent_contacts = (
        db.query(Contact)
        .filter(Contact.user_id == user.id, Contact.created_at >= recent_cutoff)
        .count()
    )
    counts["new_contacts_7d"] = recent_contacts
    if recent_contacts == 0:
        recs.append(
            _rec(
                "low",
                "Pipeline",
                "No new contacts were added in the last 7 days. Import a clean GCS list or add a buyer manually.",
                "open_contacts",
                new_contacts_7d=0,
            )
        )

    instagram_snapshot = (
        db.query(SocialMetric)
        .filter(SocialMetric.platform == "instagram", SocialMetric.metric == "snapshot")
        .order_by(SocialMetric.id.desc())
        .first()
    )
    counts["instagram_configured"] = bool(
        settings.INSTAGRAM_ACCESS_TOKEN and settings.INSTAGRAM_ACCOUNT_ID
    )
    if not counts["instagram_configured"]:
        recs.append(
            _rec(
                "low",
                "Social",
                "Instagram is in configuration-required state. Add INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID.",
                "open_social",
                snapshot=str(instagram_snapshot.captured_at) if instagram_snapshot else None,
            )
        )

    if not settings.GEMINI_API_KEY:
        recs.append(
            _rec(
                "low",
                "AI",
                "Gemini is not configured; voice transcription and LLM narrative stay in configuration-required mode.",
                "open_settings",
                configured=False,
            )
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda item: priority_order.get(item["priority"], 3))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "rules-v1",
        "llm_configured": bool(settings.GEMINI_API_KEY),
        "source": "live workspace database",
        "report_date": day,
        "counts": counts,
        "recommendations": recs,
        "erp": {
            "orders": orders.get("records", 0),
            "orders_value": orders.get("total_value", 0),
            "scheduled_qty": dispatches.get("scheduled_qty", 0),
            "dispatched_qty": dispatches.get("dispatched_qty", 0),
        },
    }


@router.get("/recommendations")
def recommendations(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = build_recommendations(db, user)
    data["recommendations"] = data["recommendations"][:limit]
    return data


@router.get("/status")
def ai_status(user: User = Depends(get_current_user)):
    return {
        "engine": "rules-v1",
        "llm_configured": bool(settings.GEMINI_API_KEY),
        "voice_slm_first": settings.VOICE_SLM_FIRST,
        "voice_slm_model": settings.voice_slm_model,
        "configured_signals": {
            "erp_sync": True,
            "visits": True,
            "voice": True,
            "team": True,
            "instagram": bool(settings.INSTAGRAM_ACCESS_TOKEN and settings.INSTAGRAM_ACCOUNT_ID),
            "linkedin": bool(settings.LINKEDIN_ACCESS_TOKEN),
        },
        "note": "Recommendations use deterministic sales rules over live rows; no fabricated metrics.",
    }


@router.get("/communication-analytics")
def communication_analytics(
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    campaigns = db.query(Campaign).filter(Campaign.user_id == user.id).all()
    messages = db.query(CampaignMessage).filter(CampaignMessage.user_id == user.id).all()
    email_status: dict[str, int] = {}
    for message in messages:
        email_status[message.status] = email_status.get(message.status, 0) + 1
    feedback = db.query(Feedback).filter(Feedback.user_id == user.id).all()
    ratings: dict[str, int] = {}
    for item in feedback:
        ratings[str(item.rating)] = ratings.get(str(item.rating), 0) + 1
    whatsapp = db.query(WhatsAppMessage).filter(WhatsAppMessage.user_id == user.id).all()
    wa_status: dict[str, int] = {}
    for item in whatsapp:
        wa_status[item.status] = wa_status.get(item.status, 0) + 1
    team = db.query(TeamMessage).filter(TeamMessage.user_id == user.id).all()
    team_status: dict[str, int] = {}
    for item in team:
        team_status[item.status] = team_status.get(item.status, 0) + 1
    voice = db.query(VoiceTranscript).filter(VoiceTranscript.user_id == user.id).all()
    sentiment: dict[str, int] = {}
    intents: dict[str, int] = {}
    for item in voice:
        s = (item.tone or {}).get("sentiment", "unknown")
        sentiment[s] = sentiment.get(s, 0) + 1
        i = (item.lead or {}).get("intent", "unknown")
        intents[i] = intents.get(i, 0) + 1
    journeys = (
        db.query(JourneyEvent.channel, func.count(JourneyEvent.id))
        .filter(JourneyEvent.user_id == user.id, JourneyEvent.created_at >= since)
        .group_by(JourneyEvent.channel)
        .all()
    )
    return {
        "days": days,
        "email": {
            "connections": db.query(EmailConnection)
            .filter(EmailConnection.user_id == user.id)
            .count(),
            "campaigns": len(campaigns),
            "campaign_messages": len(messages),
            "by_status": email_status,
            "sent": email_status.get("sent", 0),
            "failed": email_status.get("failed", 0),
            "reply_tracking": False,
        },
        "whatsapp": {"messages": len(whatsapp), "by_status": wa_status},
        "team": {"messages": len(team), "by_status": team_status},
        "voice": {"transcripts": len(voice), "sentiment": sentiment, "intent": intents},
        "feedback": {
            "responses": len(feedback),
            "average_rating": round(sum(f.rating for f in feedback) / len(feedback), 2)
            if feedback
            else 0,
            "ratings": ratings,
        },
        "journey_channels": {channel or "unknown": int(count) for channel, count in journeys},
        "configured": {
            "smtp_imap": db.query(EmailConnection)
            .filter(EmailConnection.user_id == user.id, EmailConnection.is_connected.is_(True))
            .count()
            > 0,
            "whatsapp": bool(settings.WHATSAPP_API_KEY and settings.WHATSAPP_PHONE_NUMBER_ID),
            "gemini": bool(settings.GEMINI_API_KEY),
        },
    }


@router.get("/customer/{contact_id}")
def customer_analysis(
    contact_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    contact = db.get(Contact, contact_id)
    if contact is None or (contact.user_id != user.id and not is_admin_user(user)):
        raise HTTPException(status_code=404, detail="Contact not found")
    orders = (
        db.query(ErpOrder)
        .filter(func.lower(ErpOrder.customer) == func.lower(contact.company))
        .order_by(ErpOrder.order_date.desc())
        .limit(20)
        .all()
    )
    dispatches = (
        db.query(ErpDispatch)
        .filter(func.lower(ErpDispatch.customer) == func.lower(contact.company))
        .order_by(ErpDispatch.report_date.desc())
        .limit(20)
        .all()
    )
    events = (
        db.query(JourneyEvent)
        .filter(JourneyEvent.user_id == contact.user_id, JourneyEvent.contact_id == contact.id)
        .order_by(JourneyEvent.id.desc())
        .limit(50)
        .all()
    )
    total_value = sum(float(order.total_value or 0) for order in orders)
    days_since_order = None
    if orders and orders[0].order_date:
        try:
            days_since_order = (
                datetime.now(timezone.utc).date()
                - datetime.fromisoformat(orders[0].order_date).date()
            ).days
        except ValueError:
            days_since_order = None
    negative = any((event.meta or {}).get("sentiment") == "negative" for event in events)
    customer_type = classify_customer_type(
        order_count=len(orders),
        gross_value=total_value,
        negative_sentiment=negative,
        days_since_order=days_since_order,
    )
    latest_stage = events[0].stage if events else "awareness"
    next_stage = (
        STAGES[min(STAGES.index(latest_stage) + 1, len(STAGES) - 1)]
        if latest_stage in STAGES
        else "awareness"
    )
    open_lines = sum(1 for row in dispatches if row.status != "Completed")
    recommendations = []
    if days_since_order is not None and days_since_order > 60:
        recommendations.append("Re-engage with a fresh rate card; no order in the last 60 days.")
    if open_lines:
        recommendations.append(
            f"Follow up on {open_lines} open dispatch line(s) before asking for a repeat order."
        )
    if customer_type == "high_value":
        recommendations.append("Offer a quarterly review and ask for a referral/case study.")
    elif customer_type == "new_customer":
        recommendations.append("Share the product catalogue and confirm the first requirement.")
    if negative:
        recommendations.append("Acknowledge the complaint and confirm a resolution owner/date.")
    if not recommendations:
        recommendations.append(
            "Keep the regular follow-up cadence and record the next interaction."
        )
    return {
        "contact": {
            "id": contact.id,
            "company": contact.company,
            "name": contact.name,
            "email": contact.email,
            "phone": contact.phone,
            "source": contact.source,
        },
        "customer_type": customer_type,
        "current_stage": latest_stage,
        "recommended_stage": next_stage,
        "orders": {
            "count": len(orders),
            "total_value": total_value,
            "latest_order_date": orders[0].order_date if orders else "",
            "days_since_order": days_since_order,
        },
        "dispatch": {"lines": len(dispatches), "open_lines": open_lines},
        "journey": {
            "events": len(events),
            "timeline": [
                {"stage": e.stage, "event": e.event, "channel": e.channel, "at": str(e.created_at)}
                for e in events[:12]
            ],
        },
        "recommendations": recommendations,
        "journey_summary": journey_summary(db, contact.user_id),
        "engine": "rules-v1",
    }
