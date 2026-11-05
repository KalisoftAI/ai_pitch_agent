"""Unified data sync — refresh every backend data point from GCS in one call.

Runs the ERP dispatch/orders sync, the Tally sales-register sync and the
marketing-companies sync, and reports a consolidated status so the dashboard can
stay "up and running" from a single 2-hourly refresh.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..erp_sync import sync_erp_report
from ..models import SyncRun, User
from ..security import get_current_user, require_admin
from ..services import GCSStorage
from ..tally_sync import sync_tally_sales
from .marketing_companies import DEFAULT_BUCKET, DEFAULT_PATH, _parse_workbook, _upsert_rows

router = APIRouter(prefix="/sync", tags=["sync"])

REFRESH_INTERVAL_MINUTES = 120  # 2-hour realtime refresh cadence


def _sync_graph_if_due(db: Session, user: User) -> dict:
    if settings.DEPLOY_ENV.lower() in {"prod", "production"} or settings.ENV.lower() in {"prod", "production"}:
        return {"ok": True, "skipped": True, "reason": "graph review is DEV/UAT only"}

    from .knowledge_graph import _load_graph, build_user_graph

    refresh_days = max(1, min(settings.KNOWLEDGE_GRAPH_REFRESH_DAYS, 30))
    users = db.query(User).filter(User.is_active.is_(True)).order_by(User.id.asc()).limit(100).all()
    if user.id not in {candidate.id for candidate in users}:
        users.append(user)
    due_users = []
    for candidate in users:
        previous = _load_graph(candidate.id).get("generated_at")
        if not previous:
            due_users.append(candidate)
            continue
        try:
            generated_at = datetime.fromisoformat(str(previous).replace("Z", "+00:00"))
            if generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - generated_at.astimezone(timezone.utc)
            if age >= timedelta(days=refresh_days):
                due_users.append(candidate)
        except ValueError:
            due_users.append(candidate)
    if not due_users:
        return {"ok": True, "skipped": True, "reason": "weekly interval has not elapsed", "users_checked": len(users)}

    started = datetime.now(timezone.utc)
    run = SyncRun(job="knowledge_graph_sync", status="running", detail="weekly JSON graph refresh")
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id
    try:
        completed = []
        failures = []
        for candidate in due_users:
            try:
                result = build_user_graph(candidate, db)
                completed.append({"user_id": candidate.id, "version": result["version"], "stats": result["stats"]})
            except Exception as exc:  # noqa: BLE001 - continue processing other users
                db.rollback()
                failures.append({"user_id": candidate.id, "error": type(exc).__name__})
        run = db.query(SyncRun).filter(SyncRun.id == run_id).first()
        if run:
            run.status = "warn" if failures else "ok"
            run.detail = f"built={len(completed)} failed={len(failures)} checked={len(users)}"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        return {"ok": not failures, "users_checked": len(users), "users_built": len(completed), "failures": failures, "items": completed}
    except Exception as exc:  # noqa: BLE001 - record failure and keep source sync results
        db.rollback()
        run = db.query(SyncRun).filter(SyncRun.id == run_id).first()
        if run:
            run.status = "error"
            run.detail = f"{type(exc).__name__}: {exc}"[:400]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:400], "elapsed_seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 2)}


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
    """Admin-only: refresh source data, then rebuild the graph at most weekly."""
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
    results["knowledge_graph_sync"] = _sync_graph_if_due(db, admin)
    results["ok"] = all(r.get("ok") for r in results.values())
    results["refresh_interval_minutes"] = REFRESH_INTERVAL_MINUTES
    results["knowledge_graph_refresh_days"] = max(1, min(settings.KNOWLEDGE_GRAPH_REFRESH_DAYS, 30))
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
        "knowledge_graph_sync",
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
