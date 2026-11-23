"""Unified business-KPI contract with second-level drilldown.

Backend-only: aggregates existing ERP/Tally/KPI helpers and the new Gmail/GCS
inventory tables behind a single executive response. No frontend changes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..erp_sync import dispatch_stats, forecast, latest_report_date, orders_stats
from ..models import (
    Contact,
    ErpDispatch,
    ErpOrder,
    GmailMessage,
    Product,
    ProductRate,
    User,
)
from ..routers.sales import _company_rows, _daily_rows, _delivery, _monthly_rows
from ..security import get_current_user
from ..tally_sync import tally_stats

router = APIRouter(prefix="/business-kpi", tags=["business-kpi"])


@router.get("/executive")
def executive_overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """High-level sales executive metrics with named drilldown links."""
    day = latest_report_date(db)
    dispatch = dispatch_stats(db, day)
    orders = orders_stats(db, day)
    tally = tally_stats(db)
    contacts = db.query(func.count(Contact.id)).filter(Contact.user_id == user.id).scalar() or 0
    gmail_rows = (
        db.query(func.count(GmailMessage.id)).filter(GmailMessage.user_id == user.id).scalar() or 0
    )
    gmail_attachments = sum(
        len(row or [])
        for (row,) in db.query(GmailMessage.attachments)
        .filter(GmailMessage.user_id == user.id)
        .all()
    )
    pending_rates = (
        db.query(func.count(ProductRate.id))
        .filter(ProductRate.source == "erp", ProductRate.status == "pending")
        .scalar()
        or 0
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_date": day,
        "metrics": {
            "orders_value": orders.get("total_value", 0),
            "orders_count": orders.get("records", 0),
            "scheduled_qty": dispatch.get("scheduled_qty", 0),
            "dispatched_qty": dispatch.get("dispatched_qty", 0),
            "dispatch_completion_pct": dispatch.get("completion_pct", 0),
            "tally_value": tally.get("total_value", tally.get("value", 0)),
            "contacts_total": contacts,
            "gmail_messages": gmail_rows,
            "gmail_attachments": gmail_attachments,
            "pending_erp_rates": pending_rates,
        },
        "forecast": forecast(db),
        "drilldowns": {
            "companies": "/api/business-kpi/executive/companies",
            "daily": "/api/business-kpi/executive/daily",
            "monthly": "/api/business-kpi/executive/monthly",
            "delivery": "/api/business-kpi/executive/delivery",
            "mail": "/api/business-kpi/executive/mail",
            "rates": "/api/business-kpi/executive/rates",
            "media": "/api/business-kpi/executive/media",
        },
    }


@router.get("/executive/{metric}")
def executive_detail(
    metric: str,
    limit: int = Query(default=50, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Second-level detail rows for one executive KPI."""
    name = metric.strip().lower()
    day = latest_report_date(db)
    if name == "companies":
        return {"metric": name, "rows": _company_rows(db, day)[:limit]}
    if name == "daily":
        return {"metric": name, "rows": _daily_rows(db, day, 30)[:limit]}
    if name == "monthly":
        return {"metric": name, "rows": _monthly_rows(db, day)[:limit]}
    if name == "delivery":
        return {"metric": name, "detail": _delivery(db, day)}
    if name == "orders":
        rows = (
            db.query(ErpOrder)
            .filter(ErpOrder.report_date == day)
            .order_by(ErpOrder.total_value.desc())
            .limit(limit)
            .all()
        )
        return {
            "metric": name,
            "rows": [
                {
                    "order_no": row.order_no,
                    "customer": row.customer,
                    "order_date": row.order_date,
                    "total_value": row.total_value,
                    "status": row.status,
                }
                for row in rows
            ],
        }
    if name == "dispatch":
        rows = (
            db.query(ErpDispatch)
            .filter(ErpDispatch.report_date == day)
            .order_by(ErpDispatch.schedule_qty.desc())
            .limit(limit)
            .all()
        )
        return {
            "metric": name,
            "rows": [
                {
                    "dispatch_no": row.dispatch_no,
                    "customer": row.customer,
                    "scheduled_qty": row.schedule_qty,
                    "dispatched_qty": row.dispatched_qty,
                    "status": row.status,
                }
                for row in rows
            ],
        }
    if name == "mail":
        rows = (
            db.query(GmailMessage)
            .filter(GmailMessage.user_id == user.id)
            .order_by(GmailMessage.internal_date.desc(), GmailMessage.id.desc())
            .limit(limit)
            .all()
        )
        return {
            "metric": name,
            "rows": [
                {
                    "message_id": row.message_id,
                    "thread_id": row.thread_id,
                    "subject": row.subject,
                    "client": row.client,
                    "intent": row.intent,
                    "attachments": len(row.attachments or []),
                }
                for row in rows
            ],
        }
    if name == "rates":
        rows = (
            db.query(ProductRate, Product)
            .join(Product, Product.id == ProductRate.product_id)
            .filter(ProductRate.source == "erp")
            .order_by(ProductRate.effective_date.desc(), ProductRate.id.desc())
            .limit(limit)
            .all()
        )
        return {
            "metric": name,
            "rows": [
                {
                    "product": product.name,
                    "code": product.code,
                    "rate": rate.rate,
                    "effective_date": rate.effective_date,
                    "status": rate.status,
                    "gcs_path": rate.gcs_path,
                }
                for rate, product in rows
            ],
        }
    if name == "media":
        from ..media_inventory import media_inventory

        return media_inventory(db, kind="video", limit=limit)
    raise HTTPException(status_code=404, detail=f"unknown metric: {metric}")
