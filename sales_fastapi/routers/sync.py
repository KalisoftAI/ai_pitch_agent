"""Unified data sync — refresh every backend data point from GCS in one call.

Runs the ERP dispatch/orders sync, the Tally sales-register sync and the
marketing-companies sync, and reports a consolidated status so the dashboard can
stay "up and running" from a single 2-hourly refresh.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..erp_sync import sync_erp_report
from ..models import SyncRun, User
from ..security import get_current_user, require_admin
from ..services import GCSStorage
from ..tally_sync import sync_tally_sales
from .marketing_companies import DEFAULT_BUCKET, DEFAULT_PATH, _parse_workbook, _upsert_rows

router = APIRouter(prefix="/sync", tags=["sync"])

REFRESH_INTERVAL_MINUTES = 120  # 2-hour realtime refresh cadence


def _sync_marketing(db: Session, user: User) -> dict:
    from datetime import datetime, timezone

    gcs = GCSStorage(bucket_name=DEFAULT_BUCKET)
    if not gcs.available:
        return {"ok": False, "error": "gcs_unavailable"}
    raw = gcs.download_blob(DEFAULT_PATH)
    if not raw:
        return {"ok": False, "error": "workbook_not_found"}
    run = SyncRun(job="marketing_companies_sync", status="running", detail="")
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        rows = _parse_workbook(raw)
        imported, updated, skipped = _upsert_rows(db, user.id, rows)
        db.commit()
        run.status = "ok"
        run.detail = f"imported={imported} updated={updated} skipped={skipped}"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"ok": True, "imported": imported, "updated": updated, "skipped": skipped}
    except Exception as exc:
        db.rollback()
        db.query(SyncRun).filter(SyncRun.id == run.id).update(
            {"status": "error", "detail": str(exc)[:400],
             "finished_at": datetime.now(timezone.utc)}
        )
        db.commit()
        raise


@router.post("/all")
def sync_all(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: refresh ERP, Tally and marketing data from GCS in one sweep."""
    results: dict[str, dict] = {}
    for name, fn in (
        ("erp_dispatch_sync", lambda: sync_erp_report(db)),
        ("tally_sales_sync", lambda: sync_tally_sales(db)),
        ("marketing_companies_sync", lambda: _sync_marketing(db, admin)),
    ):
        try:
            results[name] = fn()
        except Exception as exc:  # noqa: BLE001 - one failure must not block the rest
            db.rollback()
            results[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:400]}
    results["ok"] = all(r.get("ok") for r in results.values())
    results["refresh_interval_minutes"] = REFRESH_INTERVAL_MINUTES
    return results


@router.get("/status")
def sync_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Latest SyncRun per job + the configured refresh cadence."""
    jobs = (
        "erp_dispatch_sync",
        "tally_sales_sync",
        "marketing_companies_sync",
        "instore_mail_sync",
        "youtube_channel_sync",
    )
    latest: dict[str, dict] = {}
    for job in jobs:
        row = (
            db.query(SyncRun)
            .filter(SyncRun.job == job)
            .order_by(SyncRun.id.desc())
            .first()
        )
        latest[job] = (
            {
                "status": row.status,
                "started_at": str(row.started_at),
                "finished_at": str(row.finished_at) if row.finished_at else None,
            }
            if row
            else {"status": "never", "started_at": None, "finished_at": None}
        )
    return {
        "refresh_interval_minutes": REFRESH_INTERVAL_MINUTES,
        "jobs": latest,
    }
