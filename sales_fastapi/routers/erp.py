"""ERP integration API — dispatch sync, orders, forecast, rate calculator,
Google-Analytics-style metrics and YouTube Data API settings/sync.

Access model:
- read endpoints: any authenticated Kalika user (field executive, sales, admin)
- sync + settings + youtube sync: admin only (ADMIN_EMAILS, default ai.solutions@kalisoftai.in)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..erp_sync import (
    dispatch_stats, forecast, latest_report_date, orders_stats, rate_calculator, sync_erp_report,
)
from ..models import ErpDispatch, ErpOrder, IntegrationSetting, SyncRun, User
from ..security import get_current_user, require_admin

router = APIRouter(prefix="/erp", tags=["erp"])


# ---------------------------------------------------------------- models
class RateCalcIn(BaseModel):
    polymer_rate: float = Field(..., gt=1, le=1000)
    micron: float = Field(..., gt=1, le=300)
    width_mm: float = Field(..., gt=50, le=5000)
    length_m: float = Field(..., gt=10, le=20000)
    density: float = Field(default=0.92, gt=0.5, le=1.6)
    waste_pct: float = Field(default=2.0, ge=0, le=30)
    conversion_cost_per_kg: float = Field(default=18.0, ge=0, le=500)
    margin_pct: float = Field(default=8.0, ge=0, le=100)


class SettingsIn(BaseModel):
    youtube_api_key: str | None = None
    youtube_channel_id: str | None = None


class YoutubeSyncIn(BaseModel):
    channel_id: str | None = None


# ---------------------------------------------------------------- helpers
def _setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(IntegrationSetting).filter(IntegrationSetting.key == key).first()
    return row.value if row and row.value else default


def _put_setting(db: Session, key: str, value: str) -> None:
    row = db.query(IntegrationSetting).filter(IntegrationSetting.key == key).first()
    if row is None:
        row = IntegrationSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.now(timezone.utc)


def _youtube_key(db: Session) -> str:
    return _setting(db, "youtube_api_key") or settings.YOUTUBE_API_KEY


def _youtube_channel(db: Session) -> str:
    return _setting(db, "youtube_channel_id") or settings.YOUTUBE_CHANNEL_ID


# ---------------------------------------------------------------- status
@router.get("/status")
def erp_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    last_run = db.query(SyncRun).filter(SyncRun.job == "erp_dispatch_sync").order_by(SyncRun.id.desc()).first()
    return {
        "report_date": latest_report_date(db),
        "dispatch": dispatch_stats(db),
        "orders": orders_stats(db),
        "last_sync": {
            "status": last_run.status if last_run else "never",
            "started_at": str(last_run.started_at) if last_run else None,
            "finished_at": str(last_run.finished_at) if last_run else None,
            "detail": last_run.detail if last_run else "",
        } if last_run else None,
        "is_admin": (user.email or "").lower() in settings.admin_emails,
        "youtube": {
            "data_api_configured": bool(_youtube_key(db)),
            "analytics_api": "requires OAuth (next scope)",
            "channel_id": _youtube_channel(db),
        },
    }


@router.post("/sync")
def run_sync(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Pull the latest ERP report from GCS and upsert Dispatch + Orders."""
    try:
        return sync_erp_report(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # surface the sync error to the admin UI
        raise HTTPException(status_code=500, detail=f"ERP sync failed: {exc}") from exc


# ---------------------------------------------------------------- read data
@router.get("/dispatch")
def get_dispatch(status: str | None = None, limit: int = Query(default=200, ge=1, le=2000),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = latest_report_date(db)
    q = db.query(ErpDispatch).filter(ErpDispatch.report_date == day)
    if status:
        q = q.filter(ErpDispatch.status == status)
    rows = q.order_by(ErpDispatch.pct_complete.asc()).limit(limit).all()
    return [{
        "dispatch_no": r.dispatch_no, "customer": r.customer, "plant": r.plant,
        "schedule_qty": r.schedule_qty, "dispatched_qty": r.dispatched_qty,
        "balance_qty": r.balance_qty, "pct_complete": r.pct_complete, "status": r.status,
    } for r in rows]


@router.get("/orders")
def get_orders(status: str | None = None, limit: int = Query(default=200, ge=1, le=2000),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = latest_report_date(db)
    q = db.query(ErpOrder).filter(ErpOrder.report_date == day)
    if status:
        q = q.filter(ErpOrder.status == status)
    rows = q.order_by(ErpOrder.total_value.desc()).limit(limit).all()
    return [{
        "order_no": r.order_no, "customer": r.customer, "order_date": r.order_date,
        "required_date": r.required_date, "status": r.status, "total_value": r.total_value,
    } for r in rows]


@router.get("/forecast")
def get_forecast(months: int = Query(default=6, ge=1, le=24),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return forecast(db, months=months)


@router.get("/analytics")
def get_analytics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Google-Analytics-style operational metrics for the sales dashboard."""
    day = latest_report_date(db)
    d = dispatch_stats(db)
    o = orders_stats(db)
    top_customers = (db.query(ErpDispatch.customer, func.sum(ErpDispatch.dispatched_qty))
                     .filter(ErpDispatch.report_date == day)
                     .group_by(ErpDispatch.customer)
                     .order_by(func.sum(ErpDispatch.dispatched_qty).desc()).limit(8).all())
    plants = (db.query(ErpDispatch.plant, func.count())
              .filter(ErpDispatch.report_date == day).group_by(ErpDispatch.plant).all())
    return {
        "report_date": day,
        "funnel": {
            "orders": o["records"], "orders_value": o["total_value"],
            "scheduled_qty": d["scheduled_qty"], "dispatched_qty": d["dispatched_qty"],
            "completion_pct": d["completion_pct"],
        },
        "top_customers": [{"customer": c, "dispatched_qty": float(q or 0)} for c, q in top_customers],
        "plants": [{"plant": p, "records": n} for p, n in plants],
        "status_breakdown": d["by_status"],
        "pending_followup": db.query(ErpDispatch).filter(
            ErpDispatch.report_date == day,
            ErpDispatch.status != "Completed").count(),
    }


@router.post("/rate-calculator")
def calc_rate(payload: RateCalcIn, user: User = Depends(get_current_user)):
    return rate_calculator(**payload.model_dump())


# ---------------------------------------------------------------- settings (admin)
@router.get("/settings")
def get_settings(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    key = _youtube_key(db)
    return {
        "youtube_api_key_set": bool(key),
        "youtube_api_key_preview": (key[:6] + "..." + key[-4:]) if len(key) > 12 else ("set" if key else ""),
        "youtube_channel_id": _youtube_channel(db),
        "source": "database" if _setting(db, "youtube_api_key") else ("env" if settings.YOUTUBE_API_KEY else "none"),
        "admin_emails": sorted(settings.admin_emails),
        "erp_report_prefix": settings.ERP_REPORT_PREFIX,
    }


@router.put("/settings")
def put_settings(payload: SettingsIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.youtube_api_key is not None:
        _put_setting(db, "youtube_api_key", payload.youtube_api_key.strip())
    if payload.youtube_channel_id is not None:
        _put_setting(db, "youtube_channel_id", payload.youtube_channel_id.strip())
    db.commit()
    return {"ok": True, "youtube_api_key_set": bool(_youtube_key(db)),
            "youtube_channel_id": _youtube_channel(db)}


# ---------------------------------------------------------------- YouTube
@router.get("/youtube/status")
def youtube_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cached = _setting(db, "youtube_channel_stats", "")
    return {
        "data_api_configured": bool(_youtube_key(db)),
        "channel_id": _youtube_channel(db),
        "analytics_api": "YouTube Analytics API requires OAuth (next scope)",
        "cached_stats": json.loads(cached) if cached else None,
    }


@router.post("/youtube/sync")
def youtube_sync(payload: YoutubeSyncIn | None = None,
                 admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Fetch channel statistics via YouTube Data API v3 (API key).

    Analytics API (views/watch-time over time) needs OAuth and is next scope.
    """
    key = _youtube_key(db)
    channel = (payload.channel_id if payload and payload.channel_id else _youtube_channel(db))
    if not key:
        raise HTTPException(status_code=400, detail="YouTube API key not configured. Add it in ERP settings.")
    if not channel:
        raise HTTPException(status_code=400, detail="YouTube channel id not configured.")
    import requests  # local import keeps module import light

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet,statistics", "id": channel, "key": key},
            timeout=15,
        )
        data = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"YouTube API request failed: {exc}") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"YouTube API error: {data.get('error', {}).get('message', resp.text[:200])}")
    items = data.get("items") or []
    if not items:
        raise HTTPException(status_code=404, detail="Channel not found for the given id")
    item = items[0]
    stats = {
        "channel_id": item["id"],
        "title": item.get("snippet", {}).get("title", ""),
        "subscribers": int(item.get("statistics", {}).get("subscriberCount", 0) or 0),
        "views": int(item.get("statistics", {}).get("viewCount", 0) or 0),
        "videos": int(item.get("statistics", {}).get("videoCount", 0) or 0),
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    _put_setting(db, "youtube_channel_stats", json.dumps(stats))
    db.add(SyncRun(job="youtube_channel_sync", status="ok", detail=json.dumps(stats),
                   finished_at=datetime.now(timezone.utc)))
    db.commit()
    return stats
