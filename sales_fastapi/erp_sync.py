r"""ERP report sync — daily pull of Dispatch + Orders from gs://kalika_enterprises/ERP-V1/Reports.

The ERP app (D:\KaliSoftAI\ERP-System, deployed branch: master) publishes a daily
report workbook to GCS. This module mirrors the relevant sheets into the sales
app database so the sales dashboard/forecast/rate calculator can use them
without touching the ERP system itself (ERP stays read-only for us).
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from .config import settings
from .models import ErpDispatch, ErpOrder, SyncRun


# ------------------------------------------------------------------ fetch
def _local_latest() -> Path | None:
    """Prefer a local mirror (gcs_data/ERP-V1__kalika_report_*.xlsx) if present."""
    cache = Path(settings.ERP_CACHE_PATH)
    if not cache.is_absolute():
        cache = Path(__file__).resolve().parents[1] / cache
    files = sorted(cache.glob("ERP-V1__kalika_report_*.xlsx"))
    return files[-1] if files else None


def _gcs_latest() -> tuple[bytes, str]:
    import google.auth
    from google.cloud import storage

    creds, _ = google.auth.default()
    client = storage.Client(credentials=creds)
    bucket = client.bucket("kalika_enterprises")
    blobs = [
        b
        for b in client.list_blobs(bucket, prefix=settings.ERP_REPORT_PREFIX)
        if b.name.lower().endswith((".xlsx", ".xls"))
    ]
    if not blobs:
        raise FileNotFoundError(
            f"no report workbooks under gs://kalika_enterprises/{settings.ERP_REPORT_PREFIX}"
        )
    latest = sorted(blobs, key=lambda b: b.updated or datetime.min.replace(tzinfo=timezone.utc))[-1]
    return latest.download_as_bytes(), latest.name


def _report_date_from_name(name: str) -> str:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name or "")
    return m.group(1) if m else datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_report() -> tuple[dict[str, pd.DataFrame], str]:
    """Return {sheet: DataFrame} + report date. Local mirror first, then GCS."""
    local = _local_latest()
    if local is not None:
        xl = pd.ExcelFile(local)
        return {s: xl.parse(s) for s in xl.sheet_names}, _report_date_from_name(local.name)
    raw, name = _gcs_latest()
    xl = pd.ExcelFile(io.BytesIO(raw))
    return {s: xl.parse(s) for s in xl.sheet_names}, _report_date_from_name(name)


# ------------------------------------------------------------------ sync
def _num(v) -> float:
    try:
        return float(pd.to_numeric(v, errors="coerce") or 0)
    except Exception:
        return 0.0


def sync_erp_report(db: Session) -> dict:
    """Upsert Dispatch + Orders rows for the latest report date."""
    run = SyncRun(job="erp_dispatch_sync", status="running", detail="")
    db.add(run)
    db.commit()

    try:
        sheets, report_date = load_report()
        dispatch = sheets.get("Dispatch", pd.DataFrame())
        orders = sheets.get("Orders", pd.DataFrame())
        created_d = updated_d = 0
        created_o = updated_o = 0

        for _, r in dispatch.iterrows():
            no = str(r.get("Dispatch No", "")).strip()
            if not no:
                continue
            row = (
                db.query(ErpDispatch)
                .filter(ErpDispatch.report_date == report_date, ErpDispatch.dispatch_no == no)
                .first()
            )
            if row is None:
                row = ErpDispatch(report_date=report_date, dispatch_no=no)
                db.add(row)
                created_d += 1
            else:
                updated_d += 1
            row.customer = str(r.get("Customer", "")).strip()
            row.plant = str(r.get("Plant", "")).strip()
            row.sales_person = str(r.get("Sales Person", "") or "").strip()
            row.schedule_qty = _num(r.get("Schedule"))
            row.dispatched_qty = _num(r.get("Dispatched"))
            row.balance_qty = _num(r.get("Balance"))
            pct = _num(r.get("% Comp"))
            row.pct_complete = round(pct * 100, 1) if pct <= 1 else round(pct, 1)
            row.status = str(r.get("Status", "")).strip()

        for _, r in orders.iterrows():
            no = str(r.get("Order No", "")).strip()
            if not no:
                continue
            row = (
                db.query(ErpOrder)
                .filter(ErpOrder.report_date == report_date, ErpOrder.order_no == no)
                .first()
            )
            if row is None:
                row = ErpOrder(report_date=report_date, order_no=no)
                db.add(row)
                created_o += 1
            else:
                updated_o += 1
            row.customer = str(r.get("Customer", "")).strip()
            row.order_date = str(r.get("Order Date", ""))[:10]
            row.required_date = str(r.get("Required Date", ""))[:10]
            row.status = str(r.get("Status", "")).strip()
            row.total_value = _num(r.get("Total Value"))

        run.status = "ok"
        run.detail = json.dumps(
            {
                "report_date": report_date,
                "dispatch_created": created_d,
                "dispatch_updated": updated_d,
                "orders_created": created_o,
                "orders_updated": updated_o,
            }
        )
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "ok": True,
            "report_date": report_date,
            "dispatch": {"created": created_d, "updated": updated_d},
            "orders": {"created": created_o, "updated": updated_o},
        }
    except Exception as exc:
        db.rollback()
        run = db.get(SyncRun, run.id)
        if run:
            run.status = "error"
            run.detail = str(exc)[:900]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise


# ------------------------------------------------------------------ read models
def latest_report_date(db: Session) -> str:
    row = db.query(ErpDispatch.report_date).order_by(ErpDispatch.report_date.desc()).first()
    return row[0] if row else ""


def dispatch_stats(db: Session, report_date: str | None = None) -> dict:
    from sqlalchemy import func

    day = report_date or latest_report_date(db)
    if not day:
        return {
            "report_date": "",
            "records": 0,
            "scheduled_qty": 0.0,
            "dispatched_qty": 0.0,
            "completion_pct": 0,
            "by_status": {},
            "customers": 0,
        }
    q = db.query(ErpDispatch).filter(ErpDispatch.report_date == day)
    total = q.count()
    scheduled = (
        db.query(func.coalesce(func.sum(ErpDispatch.schedule_qty), 0))
        .filter(ErpDispatch.report_date == day)
        .scalar()
    )
    dispatched = (
        db.query(func.coalesce(func.sum(ErpDispatch.dispatched_qty), 0))
        .filter(ErpDispatch.report_date == day)
        .scalar()
    )
    by_status = {
        s: c
        for s, c in db.query(ErpDispatch.status, func.count())
        .filter(ErpDispatch.report_date == day)
        .group_by(ErpDispatch.status)
        .all()
    }
    return {
        "report_date": day,
        "records": total,
        "scheduled_qty": float(scheduled or 0),
        "dispatched_qty": float(dispatched or 0),
        "completion_pct": round((float(dispatched or 0) / float(scheduled) * 100), 1)
        if scheduled
        else 0,
        "by_status": by_status,
        "customers": db.query(ErpDispatch.customer)
        .filter(ErpDispatch.report_date == day)
        .distinct()
        .count(),
    }


def orders_stats(db: Session, report_date: str | None = None) -> dict:
    from sqlalchemy import func

    day = report_date or latest_report_date(db)
    if not day:
        return {"report_date": "", "records": 0, "total_value": 0.0, "by_status": {}}
    total = db.query(ErpOrder).filter(ErpOrder.report_date == day).count()
    value = (
        db.query(func.coalesce(func.sum(ErpOrder.total_value), 0))
        .filter(ErpOrder.report_date == day)
        .scalar()
    )
    by_status = {
        s: c
        for s, c in db.query(ErpOrder.status, func.count())
        .filter(ErpOrder.report_date == day)
        .group_by(ErpOrder.status)
        .all()
    }
    return {
        "report_date": day,
        "records": total,
        "total_value": float(value or 0),
        "by_status": by_status,
    }


def forecast(db: Session, months: int = 6) -> dict:
    """Monthly orders value from ERP snapshots + simple next-month projection."""
    rows = db.query(ErpOrder.order_date, ErpOrder.total_value, ErpOrder.report_date).all()
    buckets: dict[str, float] = {}
    for order_date, value, report_date in rows:
        key = (order_date or report_date or "")[:7]
        if key:
            buckets[key] = buckets.get(key, 0.0) + float(value or 0)
    ordered = sorted(buckets.items())[-months:]
    series = [{"period": k, "value": round(v, 2)} for k, v in ordered]
    values = [v for _, v in ordered]
    # naive projection: last value blended with the trailing average
    if values:
        avg = sum(values) / len(values)
        projected = round((values[-1] * 0.6) + (avg * 0.4), 2)
    else:
        projected = 0.0
    return {
        "series": series,
        "projected_next_month": projected,
        "method": "60% last month + 40% trailing average (policy-free baseline)",
    }


# ------------------------------------------------------------------ rate calculator
def rate_calculator(
    *,
    polymer_rate: float,
    micron: float,
    width_mm: float,
    length_m: float,
    density: float = 0.92,
    waste_pct: float = 2.0,
    conversion_cost_per_kg: float = 18.0,
    margin_pct: float = 8.0,
) -> dict:
    """Film/blown-film style costing.

    weight_kg = width_m x length_m x micron/1000 x density  (density g/cm3 ~ 0.92 LDPE)
    """
    width_m = width_mm / 1000.0
    weight_kg = width_m * length_m * (micron / 1000.0) * density
    gross_kg = weight_kg * (1 + waste_pct / 100.0)
    material = gross_kg * polymer_rate
    conversion = gross_kg * conversion_cost_per_kg
    cost = material + conversion
    price = cost * (1 + margin_pct / 100.0)
    return {
        "inputs": {
            "polymer_rate_per_kg": polymer_rate,
            "micron": micron,
            "width_mm": width_mm,
            "length_m": length_m,
            "density": density,
            "waste_pct": waste_pct,
            "conversion_cost_per_kg": conversion_cost_per_kg,
            "margin_pct": margin_pct,
        },
        "weight_kg": round(weight_kg, 3),
        "gross_weight_kg": round(gross_kg, 3),
        "material_cost": round(material, 2),
        "conversion_cost": round(conversion, 2),
        "total_cost": round(cost, 2),
        "price": round(price, 2),
        "price_per_kg": round(price / gross_kg, 2) if gross_kg else 0,
    }
