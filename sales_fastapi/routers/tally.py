"""Tally sales-register API: GCS sync, admin upload, dashboard and field reads."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..models import User
from ..security import get_current_user, is_admin_user, require_admin
from ..services import GCSStorage
from ..tally_sync import (
    _upload_dir,
    list_tally_sales,
    sync_tally_sales,
    tally_stats,
)

router = APIRouter(prefix="/tally", tags=["tally"])


@router.get("/status")
def tally_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        **tally_stats(db),
        "is_admin": is_admin_user(user),
        "bucket": settings.TALLY_BUCKET,
        "prefix": settings.TALLY_SALES_PREFIX,
        "cache_path": settings.TALLY_CACHE_PATH,
    }


@router.get("/overview")
def tally_overview(
    period: str | None = Query(default=None, max_length=7),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return tally_stats(db, period=period)


@router.get("/sales")
def tally_sales(
    period: str | None = Query(default=None, max_length=7),
    buyer: str = Query(default="", max_length=255),
    limit: int = Query(default=100, ge=1, le=1000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_tally_sales(db, period=period, buyer=buyer, limit=limit)


@router.post("/sync")
def tally_sync(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        result = sync_tally_sales(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tally sync failed: {exc}") from exc
    log_event(
        db,
        action="tally.sync",
        actor_user_id=admin.id,
        resource_type="tally_sales",
        resource_id="kalika_sales2026",
        status="success" if result.get("ok") else "warn",
        detail={
            "source": result.get("source"),
            "created": result.get("created"),
            "updated": result.get("updated"),
            "files": len(result.get("files") or []),
        },
        commit=True,
    )
    return result


@router.post("/upload", status_code=201)
async def tally_upload(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="A Tally .xls or .xlsx file is required")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".xls", ".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xls and .xlsx Tally exports are supported")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded Tally file is empty")
    if len(data) > settings.TALLY_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Tally file exceeds the {settings.TALLY_MAX_UPLOAD_BYTES // 1_000_000} MB limit",
        )
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(file.filename).stem)[:100] or "tally"
    safe_name = f"{stem}{suffix}"
    upload_dir = _upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / safe_name).write_bytes(data)
    gcs_uploaded = False
    try:
        gcs = GCSStorage(bucket_name=settings.TALLY_BUCKET)
        gcs_uploaded = gcs.upload_bytes(
            f"{settings.TALLY_SALES_PREFIX}{safe_name}",
            data,
            file.content_type or "application/vnd.ms-excel",
        )
    except Exception:
        gcs_uploaded = False
    try:
        result = sync_tally_sales(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tally upload sync failed: {exc}") from exc
    log_event(
        db,
        action="tally.upload",
        actor_user_id=admin.id,
        resource_type="tally_sales",
        resource_id=safe_name,
        status="success" if result.get("ok") else "warn",
        detail={"gcs_uploaded": gcs_uploaded, "rows": len(data), "source": result.get("source")},
        commit=True,
    )
    return {"uploaded": safe_name, "gcs_uploaded": gcs_uploaded, **result}
