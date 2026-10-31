"""Kalika command-center dashboard — one aggregated call for the home screen.

GET /api/dashboard/summary
  platform   -> API count, GCP services, integrations (numbers for the stat cards)
  erp        -> dispatch / orders / delivery stats + top companies (from ERP sync tables)
  social     -> YouTube / LinkedIn / Reddit / WhatsApp metrics
  voice      -> transcription pipeline numbers + tone stats
  comms      -> email connections, campaigns, outreach numbers
  team       -> pending field updates / rate reviews awaiting approval
  recommendations -> rule-based daily actions for the sales team
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..erp_sync import dispatch_stats, forecast, latest_report_date, orders_stats
from ..governance.gcp_verify import verify_environment
from ..models import (
    Campaign,
    CampaignMessage,
    Contact,
    EmailConnection,
    ErpDispatch,
    Feedback,
    LinkedInProfile,
    RedditPost,
    SyncRun,
    TeamMessage,
    User,
    VoiceTranscript,
    WhatsAppMessage,
)
from ..security import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_ROUTE_COUNT: int | None = None


def _api_count(request: Request) -> int:
    global _ROUTE_COUNT
    if _ROUTE_COUNT is None:
        _ROUTE_COUNT = len({r.path for r in request.app.routes if getattr(r, "path", "").startswith("/api")})
    return _ROUTE_COUNT


def _gcp_services() -> list[dict]:
    try:
        report = verify_environment(deep=False)
    except Exception:  # noqa: BLE001 - never break the dashboard on verify failure
        return []
    services = []
    for name, check in (report.get("checks") or {}).items():
        services.append({
            "service": name,
            "ok": bool(check.get("ok")),
            "detail": check.get("detail", ""),
        })
    return services


def _recommendations(db: Session, erp: dict, social: dict, voice: dict) -> list[dict]:
    recs: list[dict] = []
    pending = erp.get("pending_followup", 0)
    if pending:
        recs.append({
            "priority": "high", "area": "Dispatch",
            "text": f"{pending} dispatch lines are not Completed — schedule follow-up calls with those customers today.",
        })
    completion = (erp.get("funnel") or {}).get("completion_pct", 0)
    if completion and completion < 60:
        recs.append({
            "priority": "high", "area": "Delivery",
            "text": f"Delivery completion is {completion}% — below the 60% floor. Review plant-wise backlog.",
        })
    if not social.get("youtube", {}).get("cached_stats"):
        recs.append({
            "priority": "medium", "area": "YouTube",
            "text": "YouTube channel stats not synced yet — ask an admin to run YouTube sync for daily view metrics.",
        })
    if voice.get("pending_review", 0):
        recs.append({
            "priority": "medium", "area": "Field updates",
            "text": f"{voice['pending_review']} field update(s) waiting for approve/reject in the team review queue.",
        })
    stale_contacts = db.query(Contact).count()
    if stale_contacts < 50:
        recs.append({
            "priority": "low", "area": "Pipeline",
            "text": "Contact base is small — run a GCS import or scraper sweep to top up the funnel.",
        })
    if not recs:
        recs.append({"priority": "low", "area": "All clear", "text": "No blockers — keep the daily review cadence."})
    return recs


@router.get("/summary")
def dashboard_summary(request: Request, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    day = latest_report_date(db)
    d = dispatch_stats(db, day)
    o = orders_stats(db, day)

    top_customers = (db.query(ErpDispatch.customer, func.sum(ErpDispatch.dispatched_qty))
                     .filter(ErpDispatch.report_date == day)
                     .group_by(ErpDispatch.customer)
                     .order_by(func.sum(ErpDispatch.dispatched_qty).desc()).limit(6).all()) if day else []

    from ..models import IntegrationSetting
    yt_stats_row = db.query(IntegrationSetting).filter(IntegrationSetting.key == "youtube_channel_stats").first()
    youtube_stats = json.loads(yt_stats_row.value) if yt_stats_row and yt_stats_row.value else None

    linkedin_count = db.query(LinkedInProfile).count()
    reddit_count = db.query(RedditPost).count()
    wa_pending = db.query(WhatsAppMessage).filter(WhatsAppMessage.status.in_(("queued", "pending"))).count()

    vt = db.query(VoiceTranscript)
    voice_total = vt.count()
    voice_done = vt.filter(VoiceTranscript.status == "done").count()
    voice_recent = (vt.order_by(VoiceTranscript.id.desc()).limit(5).all())

    pending_field = db.query(TeamMessage).filter(TeamMessage.status == "pending").count()

    erp_block = {
        "report_date": day,
        "funnel": {
            "orders": o.get("records", 0), "orders_value": o.get("total_value", 0),
            "scheduled_qty": d.get("scheduled_qty", 0), "dispatched_qty": d.get("dispatched_qty", 0),
            "completion_pct": d.get("completion_pct", 0),
        },
        "status_breakdown": d.get("by_status", {}),
        "customers": d.get("customers", 0),
        "top_customers": [{"customer": c, "dispatched_qty": float(q or 0)} for c, q in top_customers],
        "pending_followup": db.query(ErpDispatch).filter(
            ErpDispatch.report_date == day, ErpDispatch.status != "Completed").count() if day else 0,
        "forecast": forecast(db, months=6),
    }

    social_block = {
        "youtube": {"cached_stats": youtube_stats},
        "linkedin_profiles": linkedin_count,
        "reddit_posts": reddit_count,
        "whatsapp_queued": wa_pending,
    }

    voice_block = {
        "total": voice_total, "done": voice_done,
        "pending_review": pending_field,
        "recent": [{"id": t.id, "file_name": t.file_name, "status": t.status,
                    "tone": (t.tone or {}).get("overall", ""), "created_at": str(t.created_at)}
                   for t in voice_recent],
    }

    comms_block = {
        "email_connections": db.query(EmailConnection).count(),
        "campaigns": db.query(Campaign).count(),
        "campaign_messages_sent": db.query(CampaignMessage).filter(CampaignMessage.status == "sent").count(),
        "feedback": db.query(Feedback).count(),
    }

    team_block = {
        "pending_approvals": pending_field,
        "messages_today": db.query(TeamMessage).filter(
            func.date(TeamMessage.created_at) == func.date(func.now())).count(),
    }

    last_sync = (db.query(SyncRun).filter(SyncRun.job == "erp_dispatch_sync")
                 .order_by(SyncRun.id.desc()).first())

    gcp = _gcp_services()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "api_endpoints": _api_count(request),
            "gcp_services": gcp,
            "gcp_healthy": sum(1 for s in gcp if s["ok"]),
            "env": request.app.state.db_ready and "ready" or "degraded",
            "erp_last_sync": {"status": last_sync.status, "finished_at": str(last_sync.finished_at)} if last_sync else None,
        },
        "erp": erp_block,
        "social": social_block,
        "voice": voice_block,
        "comms": comms_block,
        "team": team_block,
        "recommendations": _recommendations(db, erp_block, social_block, voice_block),
    }
