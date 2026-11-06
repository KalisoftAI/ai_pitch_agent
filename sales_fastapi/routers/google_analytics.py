"""Google Analytics (Kalika) sync for dashboard insights/stats.

Exports are expected under ``docs/kalika-google-analytics/`` in the
``kalika_enterprises`` bucket (json / csv / txt). The dashboard shows the
latest file(s) as aggregate insights and stats instead of requiring a live
Google Analytics API connection.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from io import StringIO
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services import GCSStorage

router = APIRouter(prefix="/analytics", tags=["analytics"])

GCS_BUCKET = "kalika_enterprises"
GA_PREFIX = "docs/kalika-google-analytics/"


def _summarise(parsed: Any) -> dict[str, Any] | None:
    """Turn a JSON/CSV export into a small stats + insights snapshot."""
    if isinstance(parsed, list):
        return {
            "rows": len(parsed),
            "sample": parsed[:5],
            "stats": {"rows": len(parsed)},
            "insights": [f"{len(parsed)} data rows synced from Google Analytics export."] if parsed else [],
        }
    if isinstance(parsed, dict):
        stats = {}
        insights: list[str] = []
        for key, value in parsed.items():
            if isinstance(value, (int, float)):
                stats[str(key)] = value
                if stats and len(insights) < 8:
                    insights.append(f"{key}: {value}")
            elif isinstance(value, str) and len(value) < 400:
                insights.append(f"{key}: {value}")
        return {"rows": len(parsed), "sample": parsed, "stats": stats, "insights": insights[:10]}
    return None


def _parse_csv(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(StringIO(text))
    rows = list(reader)
    return rows


@router.get("/google")
def google_analytics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),  # kept for consistency / future aggregation
):
    gcs = GCSStorage(bucket_name=GCS_BUCKET)
    if not gcs.available:
        return {
            "data_available": False,
            "source": f"gs://{GCS_BUCKET}/{GA_PREFIX}",
            "stats": {},
            "insights": ["GCS is not available, so Google Analytics exports cannot be synced right now."],
            "files": [],
            "message": "GCS is not available",
        }

    blobs = gcs.list_blobs(prefix=GA_PREFIX)
    supported = [
        b for b in blobs
        if b["name"] != GA_PREFIX and b["name"].lower().endswith((".json", ".csv", ".txt"))
    ]
    if not supported:
        return {
            "data_available": False,
            "source": f"gs://{GCS_BUCKET}/{GA_PREFIX}",
            "stats": {},
            "insights": [
                f"No Google Analytics exports found under {GA_PREFIX}. Upload the export JSON/CSV there and sync again."
            ],
            "files": [],
            "message": "No Google Analytics exports found",
        }

    supported.sort(key=lambda b: str(b.get("updated") or ""), reverse=True)
    latest = supported[0]
    raw = gcs.download_blob(latest["name"])
    parsed: Any = None
    if raw:
        lower = latest["name"].lower()
        if lower.endswith(".csv"):
            parsed = _parse_csv(raw)
        else:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = {"content": text[:5000]}

    summary = _summarise(parsed) or {"rows": 0, "sample": None, "stats": {}, "insights": []}
    if not summary["insights"]:
        summary["insights"] = [f"Synced {latest['name'].split('/')[-1]} from Google Analytics exports."]
    return {
        "data_available": True,
        "source": f"gs://{GCS_BUCKET}/{GA_PREFIX}",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "files": [
            {"name": b["name"], "size": b.get("size"), "updated": b.get("updated")}
            for b in supported[:25]
        ],
        "latest_file": latest["name"],
        "rows": summary["rows"],
        "stats": summary["stats"],
        "insights": summary["insights"],
        "sample": summary["sample"],
    }
