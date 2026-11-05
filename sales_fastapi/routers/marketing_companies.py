"""Marketing companies from the Kalika workbook.

The marketing workbook at ``sales-metadata/marketing_list_kalika.xlsx`` (in the
``kalika_enterprises`` GCS bucket) holds three overlapping company lists and a
daily-calling-log sheet. This router exposes a single clean view per user so
the workspace can filter, edit requirements and re-import without touching the
``contacts`` table.
"""

from __future__ import annotations

import re
from io import BytesIO
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
from ..models import MarketingCompany, User
from ..schemas import MarketingCompanyOut, MarketingCompanyUpdate, MarketingImportResult
from ..security import get_current_user
from ..services import GCSStorage

router = APIRouter(prefix="/marketing-companies", tags=["marketing"])

DEFAULT_BUCKET = "kalika_enterprises"
DEFAULT_PATH = "sales-contacts/RECENT_marketing_list_kalika.xlsx"


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
        ("main list", _map_main_list),
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
    company = _cell(_safe(row, _index(headers, "company")))
    category = _cell(_safe(row, _index(headers, "category")))
    call_status = _cell(_safe(row, _index(headers, "call status")))
    requirements = _cell(_safe(row, _index(headers, "requirements")))
    phone = _cell(_safe(row, _index(headers, "contact")))
    email = _cell(_safe(row, _index(headers, "email")))
    if not company:
        return None
    return {
        "company": company,
        "contact_name": "",
        "phone": phone,
        "email": email,
        "category": category or requirements,
        "call_status": call_status,
        "requirements": requirements if requirements != category else "",
    }


def _map_sheet1(headers: list[str], row: tuple) -> dict[str, Any] | None:
    name = _cell(_safe(row, _index(headers, "name")))
    category = _cell(_safe(row, _index(headers, "category")))
    call_status = _cell(_safe(row, _index(headers, "call status")))
    requirements = _cell(_safe(row, _index(headers, "requirements")))
    phone = _cell(_safe(row, _index(headers, "contact no.")))
    email = _cell(_safe(row, _index(headers, "email no.")))
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
    db: Session, user_id: int, rows: list[dict[str, Any]]
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

    for row in rows:
        company = (row.get("company") or "").strip()
        if not company:
            skipped += 1
            continue
        company_key = _normalise_company_key(company)

        target = by_key.get(company_key)
        if target is None:
            target = MarketingCompany(
                user_id=user_id,
                company=company,
                company_key=company_key,
                contact_name=row.get("contact_name") or "",
                phone=row.get("phone") or "",
                email=row.get("email") or "",
                category=row.get("category") or "",
                call_status=row.get("call_status") or "",
                requirements=row.get("requirements") or "",
                source_sheet=row.get("source_sheet") or "",
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
            new_value = row.get(field) or ""
            if new_value and not getattr(target, field):
                setattr(target, field, new_value)
                changed = True
        if not target.contact_name and (row.get("contact_name") or ""):
            target.contact_name = row["contact_name"]
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
    limit: int = Query(default=500, ge=1, le=5000),
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
    return (
        query.order_by(MarketingCompany.company.asc())
        .limit(limit)
        .all()
    )


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

    return {
        "total": base.count(),
        "with_requirements": base.filter(MarketingCompany.requirements != "").count(),
        "with_phone": base.filter(MarketingCompany.phone != "").count(),
        "with_email": base.filter(MarketingCompany.email != "").count(),
        "by_category": group(MarketingCompany.category),
        "by_call_status": group(MarketingCompany.call_status),
        "by_source": group(MarketingCompany.source_sheet),
    }


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
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value or "")
    db.commit()
    db.refresh(company)
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


@router.post("/sync")
def sync_marketing_companies(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sync marketing companies from GCS (default path)."""
    gcs = GCSStorage(bucket_name=DEFAULT_BUCKET)
    if not gcs.available:
        raise HTTPException(status_code=503, detail="GCS is not available")
    
    raw = gcs.download_blob(DEFAULT_PATH)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Marketing workbook not found at {DEFAULT_PATH}")
    
    rows = _parse_workbook(raw)
    imported, updated, skipped = _upsert_rows(db, user.id, rows)
    db.commit()
    
    return {
        "ok": True,
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "source": f"gcs://{DEFAULT_BUCKET}/{DEFAULT_PATH}",
    }
