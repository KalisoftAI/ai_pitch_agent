"""Customer feedback / follow-up triggering pipeline.

Segments (from live data):
- recent_orders  -> latest ERP-V1 report Orders sheet (kalika_report_2026-10-30.xlsx)
- new_customers  -> contacts synced from GCS sales-contacts/ in the last 7 days
- leads          -> contacts carrying call-status / requirement notes (marketing lists)

User picks a template per segment; the pipeline personalises variables and
produces wa.me click-to-send links and/or queues rows into whatsapp_messages.
QR-based sharing is intentionally NOT here yet (next scope).
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Contact, User, WhatsAppMessage
from ..pipeline_templates import (
    RATE_BLOCK,
    SEGMENT_META,
    TEMPLATES,
    fill as _fill,
    first_phone as _first_phone,
    norm_phone as _norm_phone,
    wa_link as _wa_link,
)
from ..security import get_current_user

router = APIRouter(prefix="/pipeline", tags=["feedback-pipeline"])

# ---------------------------------------------------------------- helpers
_erp_cache: dict = {"at": 0.0, "rows": []}
ERP_LOCAL = os.path.join(os.path.dirname(__file__), "..", "..", "gcs_data", "ERP-V1__kalika_report_2026-10-30.xlsx")


def _load_erp_orders() -> list[dict]:
    """Load orders from the latest ERP report (local mirror, else GCS). Cached 5 min."""
    if time.time() - _erp_cache["at"] < 300 and _erp_cache["rows"]:
        return _erp_cache["rows"]
    path = os.path.abspath(ERP_LOCAL)
    rows: list[dict] = []
    try:
        if os.path.exists(path):
            df = pd.read_excel(path, sheet_name="Orders")
        else:  # fallback: read straight from GCS with ADC
            import io
            import google.auth
            from google.cloud import storage
            creds, _ = google.auth.default()
            client = storage.Client(credentials=creds)
            blob = client.bucket("kalika_enterprises").blob("ERP-V1/Reports/kalika_report_2026-10-30.xlsx")
            df = pd.read_excel(io.BytesIO(blob.download_as_bytes()), sheet_name="Orders")
        df.columns = [str(c).strip() for c in df.columns]
        for _, r in df.iterrows():
            rows.append({
                "order_no": str(r.get("Order No", "")).strip(),
                "customer": str(r.get("Customer", "")).strip(),
                "status": str(r.get("Status", "")).strip(),
                "amount": float(pd.to_numeric(r.get("Total Value"), errors="coerce") or 0),
                "order_date": str(r.get("Order Date", ""))[:10],
            })
    except Exception:
        rows = []
    _erp_cache.update({"at": time.time(), "rows": rows})
    return rows


def _contact_phone_map(db: Session, user_id: int) -> list[Contact]:
    return db.query(Contact).filter(Contact.user_id == user_id).all()


def _segment_rows(segment: str, db: Session, user: User, limit: int) -> list[dict]:
    """Build raw audience rows for a segment: {name, company, phone, context...}."""
    contacts = _contact_phone_map(db, user.id)
    agent = user.name or "Team Kalika"

    if segment == "recent_orders":
        orders = _load_erp_orders()
        by_company = [(c, (c.company or "").lower()) for c in contacts if c.phone]
        rows = []
        for o in orders:
            cust_l = (o["customer"] or "").lower()
            phone, cname = "", ""
            if cust_l:
                for c, cl in by_company:
                    if cl and (cl in cust_l or cust_l in cl):
                        phone = _first_phone(c.phone)
                        cname = c.name
                        break
            rows.append({
                "name": cname, "company": o["customer"], "phone": phone,
                "order_no": o["order_no"], "amount": f"{o['amount']:,.0f}", "status": o["status"],
                "order_date": o["order_date"], "matched": bool(phone),
            })
        rows.sort(key=lambda r: (not r["matched"], -(r["amount"] and float(str(r["amount"]).replace(",", "")) or 0)))
        return rows[:limit]

    if segment == "new_customers":
        since = datetime.now(timezone.utc) - timedelta(days=7)
        rows = []
        for c in contacts:
            created = c.created_at
            if created is not None and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            phone = _first_phone(c.phone)
            if created and created >= since and phone:
                rows.append({"name": c.name, "company": c.company, "phone": phone,
                             "notes": (c.notes or "")[:120]})
        rows.sort(key=lambda r: r["company"] or r["name"])
        return rows[:limit]

    if segment == "leads":
        rows = []
        for c in contacts:
            phone = _first_phone(c.phone)
            notes = (c.notes or "").lower()
            if not phone:
                continue
            if "call status" in notes or "requirements" in notes or c.intent in ("sales", "procurement"):
                status = ""
                m = re.search(r"call status:\s*([^|]+)", notes)
                if m:
                    status = m.group(1).strip()
                rows.append({"name": c.name, "company": c.company, "phone": phone,
                             "call_status": status, "intent": c.intent})
        order_hint = {"not answered": 0, "busy": 1, "call later": 2, "details sent": 3}
        rows.sort(key=lambda r: order_hint.get((r["call_status"] or "").split(";")[0].lower(), 9))
        return rows[:limit]

    raise HTTPException(status_code=400, detail=f"Unknown segment '{segment}'")


# ---------------------------------------------------------------- schemas
class PreviewIn(BaseModel):
    segment: str = Field(..., pattern="^(recent_orders|new_customers|leads)$")
    template_id: str
    limit: int = Field(default=25, ge=1, le=200)


class QueueIn(PreviewIn):
    only_with_phone: bool = True


# ---------------------------------------------------------------- endpoints
@router.get("/segments")
def list_segments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for key, meta in SEGMENT_META.items():
        rows = _segment_rows(key, db, user, 500)
        reachable = sum(1 for r in rows if r.get("phone"))
        out.append({"id": key, **meta, "audience": len(rows), "with_phone": reachable,
                    "templates": [t["id"] for t in TEMPLATES[key]]})
    return out


@router.get("/templates")
def list_templates(segment: str = Query(...), user: User = Depends(get_current_user)):
    if segment not in TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unknown segment '{segment}'")
    return [{"segment": segment, **t} for t in TEMPLATES[segment]]


@router.post("/preview")
def preview(payload: PreviewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    template = next((t for t in TEMPLATES.get(payload.segment, []) if t["id"] == payload.template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found for this segment")
    agent = user.name or "Team Kalika"
    rows = _segment_rows(payload.segment, db, user, payload.limit)
    items = []
    for r in rows:
        msg = _fill(template["text"], name=r.get("name", ""), company=r.get("company", ""),
                    agent=agent, order_no=r.get("order_no", ""), amount=r.get("amount", ""),
                    status=r.get("status", ""))
        items.append({**r, "message": msg,
                      "wa_link": _wa_link(r["phone"], msg) if r.get("phone") else ""})
    return {"segment": payload.segment, "template_id": payload.template_id,
            "template_name": template["name"], "count": len(items), "items": items}


@router.post("/queue")
def queue_messages(payload: QueueIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Queue personalised messages into whatsapp_messages (status=pending).

    Human-in-the-loop kept: rows are created as 'pending'; sending still happens
    through the reviewed send path / wa.me links from the preview.
    """
    template = next((t for t in TEMPLATES.get(payload.segment, []) if t["id"] == payload.template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found for this segment")
    agent = user.name or "Team Kalika"
    rows = _segment_rows(payload.segment, db, user, payload.limit)
    queued = skipped = 0
    for r in rows:
        phone = r.get("phone") or ""
        if payload.only_with_phone and not phone:
            skipped += 1
            continue
        msg = _fill(template["text"], name=r.get("name", ""), company=r.get("company", ""),
                    agent=agent, order_no=r.get("order_no", ""), amount=r.get("amount", ""),
                    status=r.get("status", ""))
        db.add(WhatsAppMessage(user_id=user.id, phone_number=phone, message=msg, status="pending"))
        queued += 1
    db.commit()
    return {"queued": queued, "skipped_no_phone": skipped,
            "segment": payload.segment, "template_id": payload.template_id}


@router.get("/queue")
def list_queued(limit: int = Query(default=50, ge=1, le=200),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.user_id == user.id)
            .order_by(WhatsAppMessage.id.desc()).limit(limit).all())
    return [{"id": m.id, "phone": m.phone_number, "message": m.message,
             "status": m.status, "created_at": str(m.created_at),
             "wa_link": _wa_link(_first_phone(m.phone_number), m.message)} for m in rows]
