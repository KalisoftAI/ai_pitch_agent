"""GA4 "Reports snapshot" CSV parser + GCS-backed loader.

Google Analytics 4 exports a multi-section CSV (comment lines start with '#').
This module parses the sections we surface in the UI:

- totals   : active users, new users, engagement time, event count
- pages    : per-page views / users / bounce rate
- sources  : first-user source/medium and session source/medium
- cities   : active users by town/city
- retention: Nth-day new vs returning users

Everything degrades gracefully: missing file / unknown layout returns
``available: False`` with zeroed structures so the UI still renders.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from .services import GCSStorage

DEFAULT_GA4_PATH = "all-sales-contacts-data/Reports_snapshot (2).csv"


def _rows(text: str) -> list[list[str]]:
    return [row for row in csv.reader(io.StringIO(text)) if any(cell.strip() for cell in row)]


def _num(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_ga4_snapshot(text: str) -> dict[str, Any]:
    """Parse the GA4 multi-section snapshot into a UI-ready dict."""
    out: dict[str, Any] = {
        "available": False,
        "period": {"start": "", "end": ""},
        "totals": {},
        "pages": [],
        "sources": [],
        "session_sources": [],
        "cities": [],
        "retention": [],
    }
    lines = _rows(text)
    if not lines:
        return out

    # Date range appears in "# Start date: YYYYMMDD" / "# End date: ..." comments.
    for row in lines:
        first = row[0].strip()
        if first.startswith("# Start date:"):
            out["period"]["start"] = first.split(":", 1)[1].strip()
        elif first.startswith("# End date:") and not out["period"]["end"]:
            out["period"]["end"] = first.split(":", 1)[1].strip()

    section: str | None = None
    for row in lines:
        first = row[0].strip()
        if first.startswith("#"):
            section = None
            continue
        if first == "Active users" and "New users" in row:
            section = "totals"
            continue
        if first == "Page title and screen class":
            section = "pages"
            continue
        if first == "First user source / medium":
            section = "sources"
            continue
        if first == "Session source/medium":
            section = "session_sources"
            continue
        if first == "Town/City":
            section = "cities"
            continue
        if first == "Nth day":
            section = "retention"
            continue
        if section is None:
            continue

        if section == "totals":
            out["totals"] = {
                "active_users": int(_num(row[0])),
                "new_users": int(_num(row[1])) if len(row) > 1 else 0,
                "avg_engagement_seconds": round(_num(row[2]), 1) if len(row) > 2 else 0.0,
                "event_count": int(_num(row[3])) if len(row) > 3 else 0,
            }
            section = None  # totals is a single data row
        elif section == "pages" and len(row) >= 5:
            out["pages"].append(
                {
                    "title": row[0],
                    "views": int(_num(row[1])),
                    "active_users": int(_num(row[2])),
                    "event_count": int(_num(row[3])),
                    "bounce_rate": round(_num(row[4]), 3),
                }
            )
        elif section == "sources" and len(row) >= 2:
            out["sources"].append({"source": row[0], "active_users": int(_num(row[1]))})
        elif section == "session_sources" and len(row) >= 2:
            out["session_sources"].append({"source": row[0], "sessions": int(_num(row[1]))})
        elif section == "cities" and len(row) >= 2:
            out["cities"].append({"city": row[0], "active_users": int(_num(row[1]))})
        elif section == "retention" and len(row) >= 3:
            out["retention"].append(
                {
                    "day": int(_num(row[0])),
                    "new": int(_num(row[1])),
                    "returning": int(_num(row[2])),
                }
            )

    out["available"] = bool(out["totals"])
    return out


def load_ga4_snapshot(path: str | None = None, bucket: str | None = None) -> dict[str, Any]:
    """Fetch the snapshot from GCS and parse it. Never raises."""
    gcs = GCSStorage(bucket_name=bucket)
    if not gcs.available:
        return {"available": False, "reason": "gcs_unavailable"}
    blob_path = path or DEFAULT_GA4_PATH
    raw = gcs.download_blob(blob_path)
    if not raw:
        return {"available": False, "reason": "not_found", "path": blob_path}
    parsed = parse_ga4_snapshot(raw.decode("utf-8", errors="ignore"))
    parsed["source"] = f"gs://{gcs.bucket_name}/{blob_path}"
    parsed["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return parsed
