"""Marketing companies from the Kalika workbook.

The marketing workbook at ``sales-metadata/marketing_list_kalika.xlsx`` (in the
``kalika_enterprises`` GCS bucket) holds three overlapping company lists and a
daily-calling-log sheet. This router exposes a single clean view per user so
the workspace can filter, edit requirements and re-import without touching the
``contacts`` table.
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime
from io import BytesIO, StringIO
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..governance.audit import log_event
from ..models import Campaign, CampaignMessage, MarketingCompany, User
from ..schemas import (
    MarketingCompanyCreate,
    MarketingCompanyOut,
    MarketingCompanyUpdate,
    MarketingImportResult,
)
from ..security import get_current_user
from ..services import GCSStorage

router = APIRouter(prefix="/marketing-companies", tags=["marketing"])

DEFAULT_BUCKET = "kalika_enterprises"
DEFAULT_PATH = "sales-contacts/marketing_list_kalika (1).xlsx"
DEFAULT_CUSTOMERS_PATH = "sales-contacts/customers.csv"
FUNNEL_STAGES = ("awareness", "interest", "decision", "action")
SALES_PROGRESS = (
    "new",
    "video_sent",
    "catalog_sent",
    "requirements_requested",
    "rate_requested",
    "quote_sent",
    "material_sent",
)


# ----------------------------------------------------------------- helpers
def _normalise_company_key(value: str) -> str:
    clean = re.sub(r"\s+", " ", (value or "").strip())
    return clean.lower()


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text if text.lower() != "nan" else ""


def _clip(value: Any, limit: int) -> str:
    text = "" if value is None else str(value).strip()
    return text[:limit]


def _safe(row: tuple, idx: int) -> Any:
    if idx < 0 or idx >= len(row):
        return ""
    return row[idx]


def _parse_workbook(raw: bytes) -> list[dict[str, Any]]:
    """Parse the marketing workbook into a flat list of company rows.

    The workbook has three company sheets with slightly different column
    layouts. Sheet3 is a daily-calling log and is skipped.
    """
    from openpyxl import load_workbook

    workbook = load_workbook(filename=BytesIO(raw), read_only=True, data_only=True)
    sheet_map = {name.lower(): name for name in workbook.sheetnames}

    out: list[dict[str, Any]] = []

    for sheet_key, mapper in (
        ("removed duplicates - mail list", _map_mail_list),
        ("main list ", _map_main_list),
        ("sheet1", _map_sheet1),
    ):
        sheet_name = sheet_map.get(sheet_key)
        if not sheet_name:
            continue
        sheet = workbook[sheet_name]
        row_iter = sheet.iter_rows(values_only=True)
        try:
            header_row = next(row_iter)
        except StopIteration:
            continue
        headers = [_cell(value).lower() for value in header_row]
        for index, row in enumerate(row_iter, start=2):
            record = mapper(headers, row)
            if not record:
                continue
            record["source_sheet"] = sheet_name
            record["source_row"] = index
            out.append(record)

    workbook.close()
    return out


def _parse_customers_csv(raw: bytes) -> list[dict[str, Any]]:
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig", errors="replace")))
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(reader, start=2):
        values = {str(key or "").strip().lower(): value for key, value in row.items()}

        def first(*keys: str) -> str:
            return next((_cell(values.get(key)) for key in keys if _cell(values.get(key))), "")

        company = first("company", "company name", "customer", "customer name", "account", "name")
        if not company:
            continue
        rows.append(
            {
                "company": company,
                "contact_name": first("contact name", "contact person", "person", "buyer name"),
                "phone": first("phone", "phone number", "mobile", "contact", "contact no", "contact no."),
                "email": first("email", "email address", "email id", "e-mail"),
                "category": first("category", "segment", "customer type"),
                "call_status": first("call status", "status"),
                "requirements": first("requirements", "requirement", "product", "products"),
                "source_sheet": "customers.csv",
                "source_row": index,
            }
        )
    return rows


def _index(headers: list[str], *candidates: str) -> int:
    for candidate in candidates:
        target = candidate.lower()
        for idx, header in enumerate(headers):
            if header == target:
                return idx
    return -1


def _map_mail_list(headers: list[str], row: tuple) -> dict[str, Any] | None:
    name = _cell(_safe(row, _index(headers, "name")))
    category = _cell(_safe(row, _index(headers, "category")))
    call_status = _cell(_safe(row, _index(headers, "call status")))
    requirements = _cell(_safe(row, _index(headers, "requirements")))
    contact_no = _cell(_safe(row, _index(headers, "contact no.")))
    email = _cell(_safe(row, _index(headers, "email no.")))
    if not name:
        return None
    return {
        "company": name,
        "contact_name": "",
        "phone": contact_no,
        "email": email,
        "category": category or requirements,
        "call_status": call_status,
        "requirements": requirements if requirements != category else "",
    }


def _map_main_list(headers: list[str], row: tuple) -> dict[str, Any] | None:
    name = _cell(_safe(row, _index(headers, "company")))
    if not name:
        return None
    return {
        "company": name,
        "contact_name": _cell(_safe(row, _index(headers, "contact", "purchase_dept_contact"))),
        "phone": _cell(_safe(row, _index(headers, "contact", "purchase_dept_contact"))),
        "email": _cell(_safe(row, _index(headers, "email", "purchase_dept_email"))),
        "category": _cell(_safe(row, _index(headers, "category"))),
        "call_status": _cell(_safe(row, _index(headers, "call status", "call status "))),
        "requirements": _cell(_safe(row, _index(headers, "requirements"))),
    }


def _map_sheet1(headers: list[str], row: tuple) -> dict[str, Any] | None:
    name = _cell(_safe(row, _index(headers, "name")))
    category = _cell(_safe(row, _index(headers, "category", "category ")))
    call_status = _cell(_safe(row, _index(headers, "call status", "call status ")))
    requirements = _cell(_safe(row, _index(headers, "requirements")))
    phone = _cell(_safe(row, _index(headers, "contact no.")))
    email = _cell(_safe(row, _index(headers, "email no.", "email no. ")))
    if not name:
        return None
    return {
        "company": name,
        "contact_name": "",
        "phone": phone,
        "email": email,
        "category": category or requirements,
        "call_status": call_status,
        "requirements": requirements if requirements != category else "",
    }


def _upsert_rows(
    db: Session,
    user_id: int,
    rows: list[dict[str, Any]],
    *,
    refresh_source_values: bool = False,
) -> tuple[int, int, int]:
    """Insert or update rows keyed by (user_id, company_key).

    Rows that appear multiple times in the same workbook collapse into one
    company row; empty fields are filled in from later rows.
    Returns ``(imported, updated, skipped)`` counts.
    """
    imported = updated = skipped = 0

    # Load every existing row for this user in a single query instead of one
    # SELECT per company. Large marketing workbooks otherwise spend most of the
    # request budget on round trips and hit the Cloud Run timeout.
    existing_rows = (
        db.query(MarketingCompany)
        .filter(MarketingCompany.user_id == user_id)
        .all()
    )
    by_key: dict[str, MarketingCompany] = {
        row.company_key: row for row in existing_rows
    }
    pending: set[str] = set()

    limits = {
        "phone": 255,
        "email": 320,
        "category": 255,
        "call_status": 255,
        "source_sheet": 255,
        "requirements": 100_000,
        "next_action": 10_000,
    }

    for row in rows:
        company = _clip(row.get("company"), 255)
        if not company:
            skipped += 1
            continue
        company_key = _normalise_company_key(company)[:255]

        target = by_key.get(company_key)
        if target is None:
            target = MarketingCompany(
                user_id=user_id,
                company=company,
                company_key=company_key,
                contact_name=_clip(row.get("contact_name"), 255),
                phone=_clip(row.get("phone"), 255),
                email=_clip(row.get("email"), 320),
                category=_clip(row.get("category"), 255),
                call_status=_clip(row.get("call_status"), 255),
                requirements=row.get("requirements") or "",
                funnel_stage="awareness",
                sales_progress="new",
                source_sheet=_clip(row.get("source_sheet"), 255),
                source_row=int(row.get("source_row") or 0),
            )
            db.add(target)
            by_key[company_key] = target
            pending.add(company_key)
            imported += 1
            continue

        changed = False
        for field in (
            "phone",
            "email",
            "category",
            "call_status",
            "requirements",
        ):
            new_value = _clip(row.get(field), limits[field])
            if new_value and (refresh_source_values or not getattr(target, field)) and new_value != getattr(target, field):
                setattr(target, field, new_value)
                changed = True
        contact_name = _clip(row.get("contact_name"), 255)
        if contact_name and (refresh_source_values or not target.contact_name) and contact_name != target.contact_name:
            target.contact_name = contact_name
            changed = True
        source_sheet = _clip(row.get("source_sheet"), 255)
        if refresh_source_values and source_sheet and source_sheet != target.source_sheet:
            target.source_sheet = source_sheet
            target.source_row = int(row.get("source_row") or target.source_row)
            changed = True
        if changed:
            updated += 1
        elif company_key not in pending:
            skipped += 1

    return imported, updated, skipped


# ----------------------------------------------------------------- routes
@router.get("", response_model=list[MarketingCompanyOut])
def list_marketing_companies(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    call_status: str | None = Query(default=None),
    funnel_stage: str | None = Query(default=None),
    sales_progress: str | None = Query(default=None),
    due_follow_up: bool = False,
    requirements_only: bool = False,
    sort: str = Query(default="company"),
    limit: int = Query(default=25, ge=1, le=250),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(MarketingCompany).filter(MarketingCompany.user_id == user.id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            MarketingCompany.company.ilike(like)
            | MarketingCompany.contact_name.ilike(like)
            | MarketingCompany.email.ilike(like)
            | MarketingCompany.phone.ilike(like)
            | MarketingCompany.requirements.ilike(like)
        )
    if category:
        query = query.filter(MarketingCompany.category.ilike(f"%{category}%"))
    if call_status:
        query = query.filter(MarketingCompany.call_status.ilike(f"%{call_status}%"))
    if funnel_stage:
        query = query.filter(MarketingCompany.funnel_stage == funnel_stage)
    if sales_progress:
        query = query.filter(MarketingCompany.sales_progress == sales_progress)
    if due_follow_up:
        query = query.filter(
            MarketingCompany.follow_up_date != "",
            MarketingCompany.follow_up_date <= datetime.now().date().isoformat(),
        )
    if requirements_only:
        query = query.filter(MarketingCompany.requirements != "")
    order_by = {
        "company": MarketingCompany.company.asc(),
        "follow_up": MarketingCompany.follow_up_date.asc(),
        "progress": MarketingCompany.sales_progress.asc(),
        "category": MarketingCompany.category.asc(),
        "contact": MarketingCompany.contact_name.asc(),
        "updated": MarketingCompany.updated_at.desc(),
    }.get(sort, MarketingCompany.company.asc())
    return query.order_by(order_by).limit(limit).all()


@router.get("/stats")
def marketing_company_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = db.query(MarketingCompany).filter(MarketingCompany.user_id == user.id)

    def group(column):
        rows = (
            base.with_entities(column, func.count(MarketingCompany.id))
            .filter(column != "")
            .group_by(column)
            .all()
        )
        return {(value or "(none)"): count for value, count in rows}

    def domain_group():
        counts: dict[str, int] = {}
        for (email,) in base.with_entities(MarketingCompany.email).all():
            email = (email or "").strip()
            if "@" not in email:
                continue
            domain = email.rsplit("@", 1)[-1].lower().split(",")[0].split(";")[0].strip()
            if domain:
                counts[domain] = counts.get(domain, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))

    return {
        "total": base.count(),
        "with_requirements": base.filter(MarketingCompany.requirements != "").count(),
        "with_phone": base.filter(MarketingCompany.phone != "").count(),
        "with_email": base.filter(MarketingCompany.email != "").count(),
        "by_domain": domain_group(),
        "by_category": group(MarketingCompany.category),
        "by_call_status": group(MarketingCompany.call_status),
        "by_funnel_stage": group(MarketingCompany.funnel_stage),
        "by_sales_progress": group(MarketingCompany.sales_progress),
        "follow_up_due": base.filter(
            MarketingCompany.follow_up_date != "",
            MarketingCompany.follow_up_date <= datetime.now().date().isoformat(),
        ).count(),
        "by_source": group(MarketingCompany.source_sheet),
    }


@router.get("/activity")
def marketing_company_activity(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per-contact mail/campaign activity: sent, opened/viewed, failed, last touch."""
    rows = (
        db.query(CampaignMessage, Campaign.name, Campaign.channel, Campaign.created_at)
        .join(Campaign, Campaign.id == CampaignMessage.campaign_id)
        .filter(
            Campaign.user_id == user.id,
            CampaignMessage.user_id == user.id,
            CampaignMessage.contact_id != 0,
        )
        .order_by(CampaignMessage.id.desc())
        .all()
    )
    activity: dict[int, dict[str, Any]] = {}
    for message, campaign_name, channel, created_at in rows:
        item = activity.setdefault(
            message.contact_id,
            {
                "contact_id": message.contact_id,
                "sent": 0,
                "opened": 0,
                "failed": 0,
                "queued": 0,
                "last_status": "",
                "last_channel": "",
                "last_campaign": "",
                "last_subject": "",
                "last_sent_at": "",
                "last_opened_at": "",
                "last_touch_at": "",
            },
        )
        status = (message.status or "").lower()
        if status in {"sent", "opened"}:
            item["sent"] += 1
        if status == "opened":
            item["opened"] += 1
        if status == "failed":
            item["failed"] += 1
        if status in {"pending_review", "approved", "queued"}:
            item["queued"] += 1
        if not item["last_status"]:
            item["last_status"] = status
            item["last_channel"] = channel or ""
            item["last_campaign"] = campaign_name or ""
            item["last_subject"] = message.rendered_subject or ""
            item["last_sent_at"] = str(message.sent_at or "")
            item["last_touch_at"] = str(message.sent_at or created_at or "")
        if message.opened_at and not item["last_opened_at"]:
            item["last_opened_at"] = str(message.opened_at)
    return list(activity.values())


@router.patch("/{company_id}", response_model=MarketingCompanyOut)
def update_marketing_company(
    company_id: int,
    payload: MarketingCompanyUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company = (
        db.query(MarketingCompany)
        .filter(MarketingCompany.id == company_id, MarketingCompany.user_id == user.id)
        .first()
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Marketing company not found")
    changed = payload.model_dump(exclude_unset=True)
    for field, value in changed.items():
        if field == "funnel_stage" and value not in FUNNEL_STAGES:
            raise HTTPException(status_code=422, detail="Invalid funnel stage")
        if field == "sales_progress" and value not in SALES_PROGRESS:
            raise HTTPException(status_code=422, detail="Invalid sales progress")
        if field == "follow_up_date" and value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise HTTPException(status_code=422, detail="Follow-up date must use YYYY-MM-DD")
        if field == "follow_up_date" and value:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Follow-up date must be a valid date") from exc
        setattr(company, field, value or "")
    log_event(
        db,
        action="marketing_company.update",
        actor_user_id=user.id,
        resource_type="marketing_company",
        resource_id=str(company.id),
        tenant_id=user.domain,
        detail={"fields": sorted(changed)},
    )
    db.commit()
    db.refresh(company)
    return company


@router.post("", response_model=MarketingCompanyOut, status_code=201)
def create_marketing_company(
    payload: MarketingCompanyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.funnel_stage not in FUNNEL_STAGES:
        raise HTTPException(status_code=422, detail="Invalid funnel stage")
    if payload.sales_progress not in SALES_PROGRESS:
        raise HTTPException(status_code=422, detail="Invalid sales progress")
    if payload.follow_up_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", payload.follow_up_date):
        raise HTTPException(status_code=422, detail="Follow-up date must use YYYY-MM-DD")
    company_key = _normalise_company_key(payload.company)
    if not company_key:
        raise HTTPException(status_code=422, detail="Company name is required")

    company = MarketingCompany(
        user_id=user.id,
        company=payload.company.strip(),
        company_key=company_key,
        contact_name=payload.contact_name.strip(),
        phone=payload.phone.strip(),
        email=payload.email.strip(),
        category=payload.category.strip(),
        call_status=payload.call_status.strip(),
        requirements=payload.requirements.strip(),
        funnel_stage=payload.funnel_stage or "awareness",
        sales_progress=payload.sales_progress or "new",
        next_action=payload.next_action.strip(),
        follow_up_date=payload.follow_up_date or "",
        source_sheet="manual",
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    log_event(
        db,
        action="marketing_company.create",
        actor_user_id=user.id,
        resource_type="marketing_company",
        resource_id=str(company.id),
        tenant_id=user.domain,
        detail={"company": company.company},
    )
    return company


@router.post("/import", response_model=MarketingImportResult)
async def import_marketing_companies(
    request: Request,
    file: UploadFile | None = File(default=None),
    bucket: str = Form(default=""),
    path: str = Form(default=""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import the marketing workbook into the per-user marketing table.

    The default source is ``kalika_enterprises/sales-metadata/marketing_list_kalika.xlsx``.
    Attach a local workbook via ``file`` or override the GCS path with ``path``
    (and optional ``bucket``).
    """
    raw: bytes | None = None
    source_label = ""

    if file is not None and file.filename:
        raw = await file.read()
        source_label = f"upload:{file.filename}"
    else:
        target_bucket = bucket.strip() or DEFAULT_BUCKET
        target_path = path.strip() or DEFAULT_PATH
        gcs = GCSStorage(bucket_name=target_bucket)
        if not gcs.available:
            raise HTTPException(status_code=503, detail="GCS is not available")
        raw = gcs.download_blob(target_path)
        source_label = f"gcs://{target_bucket}/{target_path}"

    if not raw:
        raise HTTPException(status_code=404, detail="Marketing workbook not found")

    rows = _parse_workbook(raw)
    imported, updated, skipped = _upsert_rows(db, user.id, rows)
    db.commit()

    sheets = sorted({(row.get("source_sheet") or "") for row in rows if row.get("source_sheet")})
    return MarketingImportResult(
        ok=True,
        imported=imported,
        updated=updated,
        skipped=skipped,
        source=source_label,
        sheets=sheets,
    )


@router.get("/source-info")
def marketing_source_info(user: User = Depends(get_current_user)):
    """Report the size and type of the default marketing workbook."""
    gcs = GCSStorage(bucket_name=DEFAULT_BUCKET)
    if not gcs.available or gcs._client is None:
        raise HTTPException(status_code=503, detail="GCS is not available")
    try:
        blob = gcs._client.bucket(DEFAULT_BUCKET).blob(DEFAULT_PATH)
        if not blob.exists():
            return {"exists": False, "path": DEFAULT_PATH}
        blob.reload()
        return {
            "exists": True,
            "path": DEFAULT_PATH,
            "size_bytes": blob.size,
            "size_mb": round((blob.size or 0) / (1024 * 1024), 2),
            "content_type": blob.content_type,
            "updated": str(blob.updated),
        }
    except Exception as exc:  # pragma: no cover - diagnostics
        raise HTTPException(
            status_code=500, detail=f"source-info failed: {type(exc).__name__}: {exc}"
        ) from exc


@router.post("/sync")
def sync_marketing_companies(
    source: str = Query(default="all"),
    path: str = Query(default=""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sync the latest marketing workbook and/or customers CSV from GCS.

    Pass ``path`` to override the default workbook object key with your own
    upload path (e.g. ``sales-contacts/my_updated_list.xlsx``).
    """
    if source not in {"all", "marketing", "customers"}:
        raise HTTPException(status_code=400, detail="Source must be all, marketing, or customers")
    gcs = GCSStorage(bucket_name=DEFAULT_BUCKET)
    if not gcs.available:
        raise HTTPException(status_code=503, detail="GCS is not available")

    custom_path = (path or "").strip()
    paths = []
    if custom_path:
        parser = _parse_customers_csv if custom_path.lower().endswith(".csv") else _parse_workbook
        paths.append((custom_path, parser))
        source = "custom"
    else:
        if source in {"all", "marketing"}:
            paths.append((DEFAULT_PATH, _parse_workbook))
        if source in {"all", "customers"}:
            paths.append((DEFAULT_CUSTOMERS_PATH, _parse_customers_csv))
    rows: list[dict[str, Any]] = []
    synced_sources: list[str] = []
    errors: list[str] = []
    for path, parser in paths:
        raw = gcs.download_blob(path)
        if not raw:
            errors.append(f"Source not found: {path}")
            continue
        try:
            parsed_rows = parser(raw)
            rows.extend(parsed_rows)
            synced_sources.append(path)
        except Exception as exc:
            errors.append(f"Parse failed for {path}: {type(exc).__name__}")
    if not synced_sources:
        raise HTTPException(status_code=404, detail="; ".join(errors) or "No GCS sources found")

    try:
        imported, updated, skipped = _upsert_rows(
            db, user.id, rows, refresh_source_values=True
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"db failed: {type(exc).__name__}: {exc}",
        ) from exc

    return {
        "ok": True,
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "rows_parsed": len(rows),
        "sources": [f"gs://{DEFAULT_BUCKET}/{path}" for path in synced_sources],
        "warnings": errors,
    }
