"""Tally Sales Register sync.

Reads ``gs://kalika_enterprises/kalika_sales2026/*.xls`` (or the local mirror in
``gcs_data``) and mirrors each invoice line into ``tally_sales`` so the dashboard
and field views can show real buyer sales without touching Tally or the ERP.
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import settings
from .models import SyncRun, TallySale

_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
_HEADER_NAMES = {
    "date": "date",
    "particulars": "particulars",
    "buyer": "buyer",
    "buyer address": "buyer_address",
    "consignee": "consignee",
    "voucher type": "voucher_type",
    "voucher no": "voucher_no",
    "voucher no.": "voucher_no",
    "gstin uin": "gstin",
    "gstin/uin": "gstin",
    "quantity": "quantity",
    "rate": "rate",
    "value": "value",
    "gross total": "gross_total",
    "sales gst": "sales_gst",
}


def _repo_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return path


def _cache_dir() -> Path:
    return _repo_path(settings.TALLY_CACHE_PATH)


def _upload_dir() -> Path:
    return _repo_path(settings.TALLY_UPLOAD_DIR)


def _source_name(path: Path) -> str:
    name = path.name
    if name.startswith("kalika_sales2026__"):
        return name.split("__", 1)[1]
    return name


def _local_sources() -> list[tuple[str, Path]]:
    files = sorted(_cache_dir().glob("kalika_sales2026__*.xls*"))
    upload_dir = _upload_dir()
    if upload_dir.exists():
        files.extend(sorted(upload_dir.glob("*.xls*")))
    out: dict[str, Path] = {}
    for path in files:
        out[_source_name(path)] = path
    return sorted(out.items())


def _gcs_sources() -> list[tuple[str, bytes]]:
    import google.auth
    from google.cloud import storage

    creds, _ = google.auth.default()
    client = storage.Client(credentials=creds)
    bucket = client.bucket(settings.TALLY_BUCKET)
    blobs = [
        blob
        for blob in client.list_blobs(bucket, prefix=settings.TALLY_SALES_PREFIX)
        if blob.name.lower().endswith((".xls", ".xlsx"))
    ]
    if not blobs:
        raise FileNotFoundError(
            f"no Tally workbooks under gs://{settings.TALLY_BUCKET}/"
            f"{settings.TALLY_SALES_PREFIX}"
        )
    return [(Path(blob.name).name, blob.download_as_bytes()) for blob in blobs]


def _load_sources() -> tuple[str, list[tuple[str, Path | bytes]]]:
    local = _local_sources()
    if local:
        return "local", list(local)
    return "gcs", _gcs_sources()


def _text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).replace("_x000D_", " ").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def _num(value) -> float:
    if value is None:
        return 0.0
    try:
        if pd.isna(value):
            return 0.0
    except (TypeError, ValueError):
        pass
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("Rs", "").replace("₹", "").strip()
    if not text:
        return 0.0
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        number = float(text)
    except ValueError:
        return 0.0
    return -number if negative else number


def _date(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (int, float)) and 20000 < float(value) < 60000:
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(value))).strftime("%Y-%m-%d")
    text = str(value).strip()
    try:
        if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", text):
            return pd.to_datetime(text).strftime("%Y-%m-%d")
        return pd.to_datetime(value, dayfirst=True).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return ""


def _period_from_name(name: str) -> str:
    match = re.search(r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*[-_ ]?(\d{2,4})", name.upper())
    if not match:
        return ""
    month = _MONTHS[match.group(1)]
    year = int(match.group(2))
    if year < 100:
        year += 2000
    return f"{year:04d}-{month:02d}"


def _header_map(df: pd.DataFrame) -> tuple[int, dict[str, int]] | None:
    for row_idx in range(min(40, len(df))):
        mapping: dict[str, int] = {}
        for col_idx, raw in enumerate(df.iloc[row_idx].tolist()):
            key = re.sub(r"[^a-z0-9/]+", " ", _text(raw).lower()).strip()
            key = _HEADER_NAMES.get(key, key)
            if key and key not in mapping:
                mapping[key] = col_idx
        if "date" in mapping and "particulars" in mapping:
            return row_idx, mapping
    return None


def _value(row, mapping: dict[str, int], name: str):
    index = mapping.get(name)
    return row.iloc[index] if index is not None else None


def _sheet_name(xl: pd.ExcelFile) -> str:
    for name in xl.sheet_names:
        if name.strip().lower() == "sales register":
            return name
    return xl.sheet_names[0]


def parse_tally_workbook(data: Path | bytes, source_name: str) -> list[dict]:
    """Parse one Tally workbook into invoice-line rows."""
    xl = pd.ExcelFile(data if isinstance(data, Path) else io.BytesIO(data))
    df = xl.parse(_sheet_name(xl), header=None)
    if df.empty:
        return []
    header = _header_map(df)
    if header is None:
        raise ValueError(f"{source_name}: Sales Register header not found")
    header_row, mapping = header
    fallback_period = _period_from_name(source_name)
    rows: list[dict] = []
    invoice: dict | None = None

    def close_invoice() -> None:
        nonlocal invoice
        if invoice is None:
            return
        current = invoice
        invoice = None
        if current["cancelled"]:
            return
        items = current["items"]
        if not items and current["header_item"] is not None:
            items = [current["header_item"]]
        if not items:
            return
        invoice_value = current["invoice_value"]
        invoice_total = current["invoice_total"] or invoice_value
        if not invoice_total:
            invoice_total = sum(_num(item["value"]) for item in items)
        tax = current["tax"]
        if not tax and invoice_total and invoice_value:
            tax = max(0.0, invoice_total - invoice_value)
        if invoice_total and not any(_num(item["value"]) for item in items):
            items[0]["value"] = invoice_total
        for item in items:
            value = _num(item["value"])
            quantity = _num(item["quantity"])
            rate = _num(item["rate"])
            if not rate and quantity and value:
                rate = value / quantity
            period = (current["sale_date"] or fallback_period)[:7]
            rows.append(
                {
                    "source_file": source_name,
                    "source_row": int(item["row"]) + 1,
                    "sale_date": current["sale_date"],
                    "period": period,
                    "buyer": current["buyer"],
                    "buyer_address": current["buyer_address"],
                    "consignee": current["consignee"],
                    "gstin": current["gstin"],
                    "voucher_type": current["voucher_type"],
                    "voucher_no": current["voucher_no"],
                    "item_name": _text(item["particulars"]),
                    "quantity": round(quantity, 3),
                    "rate": round(rate, 3),
                    "value": round(value, 2),
                    "invoice_total": round(invoice_total, 2),
                    "tax": round(tax, 2),
                }
            )

    for row_idx in range(header_row + 1, len(df)):
        row = df.iloc[row_idx]
        sale_date = _date(_value(row, mapping, "date"))
        particulars = _text(_value(row, mapping, "particulars"))
        buyer = _text(_value(row, mapping, "buyer"))
        voucher_no = _text(_value(row, mapping, "voucher_no"))
        if sale_date:
            close_invoice()
            if not voucher_no and not buyer:
                continue
            cancelled = "cancel" in particulars.lower() or "cancel" in buyer.lower()
            invoice = {
                "sale_date": sale_date,
                "buyer": buyer,
                "buyer_address": _text(_value(row, mapping, "buyer_address")),
                "consignee": _text(_value(row, mapping, "consignee")),
                "gstin": _text(_value(row, mapping, "gstin")),
                "voucher_type": _text(_value(row, mapping, "voucher_type")),
                "voucher_no": voucher_no or f"row-{row_idx + 1}",
                "invoice_value": _num(_value(row, mapping, "value")),
                "invoice_total": _num(_value(row, mapping, "gross_total"))
                or _num(_value(row, mapping, "value")),
                "tax": 0.0,
                "cancelled": cancelled,
                "header_item": None,
                "items": [],
            }
            quantity = _num(_value(row, mapping, "quantity"))
            rate = _num(_value(row, mapping, "rate"))
            value = _num(_value(row, mapping, "value"))
            if particulars or quantity or rate or value:
                invoice["header_item"] = {
                    "row": row_idx,
                    "particulars": particulars or buyer,
                    "quantity": quantity,
                    "rate": rate,
                    "value": value,
                }
            continue
        if invoice is None:
            continue
        quantity = _num(_value(row, mapping, "quantity"))
        rate = _num(_value(row, mapping, "rate"))
        value = _num(_value(row, mapping, "value"))
        if particulars or quantity or rate or value:
            invoice["items"].append(
                {
                    "row": row_idx,
                    "particulars": particulars,
                    "quantity": quantity,
                    "rate": rate,
                    "value": value,
                }
            )
    close_invoice()
    return rows


def sync_tally_sales(db: Session) -> dict:
    """Upsert every Tally Sales Register line from GCS/local mirror."""
    run = SyncRun(job="tally_sales_sync", status="running", detail="")
    db.add(run)
    db.commit()
    run_id = run.id

    try:
        source_kind, sources = _load_sources()
        if not sources:
            raise FileNotFoundError(
                f"no Tally workbooks in {settings.TALLY_CACHE_PATH} or "
                f"gs://{settings.TALLY_BUCKET}/{settings.TALLY_SALES_PREFIX}"
            )
        created = updated = deleted = 0
        errors: list[str] = []
        files: list[dict] = []
        periods: set[str] = set()
        for source_name, payload in sources:
            try:
                parsed = parse_tally_workbook(payload, source_name)
            except Exception as exc:  # noqa: BLE001 - one bad workbook must not block the rest
                errors.append(f"{source_name}: {exc}")
                continue
            existing = {
                row.source_row: row
                for row in db.query(TallySale).filter(TallySale.source_file == source_name).all()
            }
            seen: set[int] = set()
            for item in parsed:
                key = int(item["source_row"])
                seen.add(key)
                row = existing.get(key)
                if row is None:
                    row = TallySale(source_file=source_name, source_row=key)
                    db.add(row)
                    created += 1
                else:
                    updated += 1
                for field, value in item.items():
                    setattr(row, field, value)
                periods.add(item["period"])
            for key, row in existing.items():
                if key not in seen:
                    db.delete(row)
                    deleted += 1
            files.append({"source_file": source_name, "rows": len(parsed)})
        if not created and not updated and errors:
            raise ValueError("; ".join(errors))
        run.status = "warn" if errors else "ok"
        run.detail = json.dumps(
            {
                "source": source_kind,
                "files": files,
                "created": created,
                "updated": updated,
                "deleted": deleted,
                "periods": sorted(periods),
                "errors": errors,
            }
        )
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "ok": not errors,
            "source": source_kind,
            "files": files,
            "created": created,
            "updated": updated,
            "deleted": deleted,
            "periods": sorted(periods),
            "errors": errors,
        }
    except Exception as exc:
        db.rollback()
        failed = db.get(SyncRun, run_id)
        if failed:
            failed.status = "error"
            failed.detail = str(exc)[:900]
            failed.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise


def latest_tally_period(db: Session) -> str:
    row = db.query(TallySale.period).order_by(TallySale.period.desc()).first()
    return row[0] if row else ""


def _last_sync(db: Session) -> dict | None:
    row = (
        db.query(SyncRun)
        .filter(SyncRun.job == "tally_sales_sync")
        .order_by(SyncRun.id.desc())
        .first()
    )
    if row is None:
        return None
    return {
        "status": row.status,
        "started_at": str(row.started_at) if row.started_at else None,
        "finished_at": str(row.finished_at) if row.finished_at else None,
        "detail": row.detail or "",
    }


def tally_stats(db: Session, period: str | None = None) -> dict:
    latest = latest_tally_period(db)
    selected = period or latest
    base = db.query(TallySale)
    if selected:
        base = base.filter(TallySale.period == selected)
    records = base.count()
    total_value = base.with_entities(func.coalesce(func.sum(TallySale.value), 0)).scalar() or 0
    total_quantity = base.with_entities(func.coalesce(func.sum(TallySale.quantity), 0)).scalar() or 0
    invoices = (
        base.with_entities(TallySale.source_file, TallySale.voucher_no).distinct().count()
    )
    customers = base.with_entities(func.count(func.distinct(TallySale.buyer))).scalar() or 0
    latest_sale_date = base.with_entities(func.max(TallySale.sale_date)).scalar() or ""
    top_buyers = [
        {
            "buyer": buyer or "(unknown)",
            "value": round(float(value or 0), 2),
            "quantity": round(float(quantity or 0), 2),
            "invoices": int(count or 0),
        }
        for buyer, value, quantity, count in (
            base.with_entities(
                TallySale.buyer,
                func.coalesce(func.sum(TallySale.value), 0),
                func.coalesce(func.sum(TallySale.quantity), 0),
                func.count(func.distinct(TallySale.voucher_no)),
            )
            .group_by(TallySale.buyer)
            .order_by(func.coalesce(func.sum(TallySale.value), 0).desc())
            .limit(8)
            .all()
        )
    ]
    monthly = [
        {
            "period": item_period,
            "value": round(float(value or 0), 2),
            "invoices": int(count or 0),
        }
        for item_period, value, count in (
            db.query(
                TallySale.period,
                func.coalesce(func.sum(TallySale.value), 0),
                func.count(func.distinct(TallySale.voucher_no)),
            )
            .filter(TallySale.period != "")
            .group_by(TallySale.period)
            .order_by(TallySale.period)
            .all()
        )
    ]
    periods = [
        row[0]
        for row in db.query(TallySale.period)
        .filter(TallySale.period != "")
        .distinct()
        .order_by(TallySale.period.desc())
        .all()
    ]
    return {
        "data_available": records > 0,
        "period": selected,
        "periods": periods,
        "latest_sale_date": latest_sale_date,
        "records": records,
        "invoices": invoices,
        "customers": int(customers),
        "total_value": round(float(total_value or 0), 2),
        "total_quantity": round(float(total_quantity or 0), 2),
        "average_invoice_value": round(float(total_value or 0) / invoices, 2) if invoices else 0,
        "source_files": base.with_entities(TallySale.source_file).distinct().count(),
        "top_buyers": top_buyers,
        "monthly": monthly,
        "last_sync": _last_sync(db),
    }


def list_tally_sales(
    db: Session, period: str | None = None, buyer: str = "", limit: int = 100
) -> list[dict]:
    query = db.query(TallySale)
    selected = period or latest_tally_period(db)
    if selected:
        query = query.filter(TallySale.period == selected)
    if buyer:
        query = query.filter(TallySale.buyer.ilike(f"%{buyer}%"))
    rows = (
        query.order_by(TallySale.sale_date.desc(), TallySale.value.desc()).limit(limit).all()
    )
    return [
        {
            "id": row.id,
            "source_file": row.source_file,
            "sale_date": row.sale_date,
            "period": row.period,
            "buyer": row.buyer,
            "gstin": row.gstin,
            "voucher_no": row.voucher_no,
            "item_name": row.item_name,
            "quantity": row.quantity,
            "rate": row.rate,
            "value": row.value,
            "invoice_total": row.invoice_total,
            "tax": row.tax,
        }
        for row in rows
    ]
