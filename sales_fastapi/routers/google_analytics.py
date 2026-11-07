"""Google Analytics (Kalika) sync for dashboard insights/stats.

Exports are expected under ``docs/kalika-google-analytics/`` in the
``kalika_enterprises`` bucket (json / csv / txt). Processing happens only when
``POST /analytics/google/sync`` detects a new or changed export; the parsed
insights (cities, countries, devices, sources, pages, totals, date range) are
stored in ``sales-metadata/sales-app-data/ga_insights.json`` so ``GET`` reads
are cache-first and never touch Cloud SQL.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from ..ga_insights import (
    build_summary,
    files_signature,
    parse_rows_from_csv,
    parse_rows_from_json,
)
from ..services import AppDataStore, GCSStorage

router = APIRouter(prefix="/analytics", tags=["analytics"])

GCS_BUCKET = "kalika_enterprises"
GA_PREFIX = "docs/kalika-google-analytics/"
SUPPORTED_SUFFIXES = (".json", ".csv", ".txt")
MAX_FILES_PER_SYNC = 10


def _supported_files(gcs: GCSStorage) -> list[dict[str, Any]]:
    blobs = gcs.list_blobs(prefix=GA_PREFIX, suffixes=SUPPORTED_SUFFIXES)
    files = [b for b in blobs if b["name"] != GA_PREFIX]
    files.sort(key=lambda b: str(b.get("updated") or ""))
    return files


def _parse(name: str, raw: bytes) -> list[dict[str, Any]]:
    if name.lower().endswith(".csv"):
        return parse_rows_from_csv(raw)
    if name.lower().endswith(".json"):
        return parse_rows_from_json(raw) or []
    return []


@router.get("/google")
def google_analytics():
    """Cache-first insights: read ``sales-app-data/ga_insights.json`` only.

    When exports exist but were never processed (or changed), the payload asks
    the UI to trigger Sync — no downloads happen here.
    """
    store = AppDataStore()
    cached = None
    if store.available:
        try:
            cached = store.load("ga_insights")
        except Exception:
            cached = None
    if cached and cached.get("stats"):
        payload = dict(cached)
        payload["from_cache"] = True
        return payload

    gcs = GCSStorage(bucket_name=GCS_BUCKET)
    if not gcs.available:
        return {
            "data_available": False,
            "source": f"gs://{GCS_BUCKET}/{GA_PREFIX}",
            "stats": {},
            "insights": [],
            "files": [],
            "message": "GCS is not available, so Google Analytics exports cannot be synced right now.",
        }
    files = _supported_files(gcs)
    if not files:
        return {
            "data_available": False,
            "source": f"gs://{GCS_BUCKET}/{GA_PREFIX}",
            "stats": {},
            "insights": [],
            "files": [],
            "message": (
                f"No Google Analytics exports found under {GA_PREFIX}. "
                "Upload the GA4 export (CSV/JSON) there, then press GA Sync."
            ),
        }
    return {
        "data_available": False,
        "needs_sync": True,
        "source": f"gs://{GCS_BUCKET}/{GA_PREFIX}",
        "stats": {},
        "insights": [],
        "files": [
            {"name": b["name"], "size": b.get("size"), "updated": b.get("updated")}
            for b in files[-25:]
        ],
        "message": "GA export(s) are present but not processed yet — press GA Sync to build insights.",
    }


@router.post("/google/sync")
def google_analytics_sync(force: bool = False):
    """Detect new/changed exports; process only then.

    * No change since last sync -> ``status=no_new_files`` (message for the UI,
      previously stored insights are returned untouched, nothing re-read).
    * New/changed file(s)      -> parse them (latest first, capped), rebuild
      insights, store into ``sales-app-data/`` and return the fresh summary.
    * ``force=True``           -> re-read and rebuild even with no new files
      (used after parser changes or to refresh on demand).
    """
    store = AppDataStore()
    gcs = GCSStorage(bucket_name=GCS_BUCKET)
    if not gcs.available:
        return {"status": "error", "message": "GCS is not available", "data_available": False}

    files = _supported_files(gcs)
    if not files:
        return {
            "status": "no_files",
            "message": f"No GA exports under {GA_PREFIX}. Upload a GA4 CSV/JSON export first.",
            "data_available": False,
            "files": [],
        }

    signature = files_signature(files)
    state: dict[str, Any] = {}
    if not force and store.available:
        try:
            state = store.load("ga_state") or {}
        except Exception:
            state = {}

    if not force and state.get("signature") == signature:
        cached: dict[str, Any] = {}
        if store.available:
            try:
                cached = store.load("ga_insights") or {}
            except Exception:
                cached = {}
        payload = dict(cached)
        payload.update(
            {
                "status": "no_new_files",
                "message": (
                    "No new file detected — showing insights from the last processed export"
                    + (f" ({str(state.get('processed_at') or '')[:10]})." if state.get("processed_at") else ".")
                ),
                "files": [
                    {"name": b["name"], "size": b.get("size"), "updated": b.get("updated")}
                    for b in files[-25:]
                ],
            }
        )
        payload.setdefault("data_available", bool(payload.get("stats")))
        return payload

    known_entries = {f"{n}|{u}" for n, u in (state.get("entries") or [])}
    new_files = [
        b for b in files
        if f"{b['name']}|{b.get('updated')}" not in known_entries
    ] or files
    to_process = sorted(files, key=lambda b: str(b.get("updated") or ""))[-MAX_FILES_PER_SYNC:]

    file_rows: list[tuple[str, list[dict[str, Any]]]] = []
    read_errors: list[str] = []
    for entry in to_process:
        name = str(entry["name"])
        try:
            raw = gcs.download_blob(name)
            if not raw:
                read_errors.append(f"{name}: empty/unreadable")
                continue
            file_rows.append((name.split("/")[-1], _parse(name, raw)))
        except Exception as exc:  # pragma: no cover - defensive
            read_errors.append(f"{name}: {type(exc).__name__}")

    now = datetime.now(timezone.utc).isoformat()
    summary = build_summary(file_rows, source=f"gs://{GCS_BUCKET}/{GA_PREFIX}", synced_at=now)
    summary["status"] = "processed"
    summary["new_files"] = [b["name"].split("/")[-1] for b in new_files][:MAX_FILES_PER_SYNC]
    if read_errors:
        summary["warnings"] = read_errors

    if store.available:
        try:
            store.save("ga_insights", summary)
            store.save(
                "ga_state",
                {
                    "signature": signature,
                    "processed_at": now,
                    "entries": [[b["name"], b.get("updated")] for b in files],
                    "files_count": len(files),
                },
            )
        except Exception:
            pass
    return summary
