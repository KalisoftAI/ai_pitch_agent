"""Google Analytics export -> insights utility.

Parses GA4 / Looker-Studio style exports (CSV, JSON) placed under
``gs://kalika_enterprises/docs/kalika-google-analytics/`` and produces a
compact summary: totals, date range, top groups (cities, countries, devices,
sources, pages, browsers, ...) and human-readable insight lines.

Results are stored in the GCS app-data cache
(``sales-metadata/sales-app-data/ga_insights.json``) so the dashboard can read
them without touching Cloud SQL or re-downloading exports. The router calls
:func:`build_summary` only when a new/changed export is detected.
"""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any

DIMENSION_GROUPS: dict[str, tuple[str, ...]] = {
    "Cities": ("city", "town / city", "town/city", "city (town / city)", "district"),
    "Countries": ("country", "country / territory", "country/territory", "territory"),
    "Regions": ("region", "continent", "sub continent", "subcontinent"),
    "Devices": ("device category", "device info", "mobile device", "device"),
    "Sources": (
        "session source / medium",
        "source / medium",
        "first user source / medium",
        "channel group",
        "session medium",
        "session source",
        "source",
    ),
    "Pages": (
        "landing page",
        "page path and screen class",
        "page location",
        "page title",
        "landing page (expanded)",
        "page path",
    ),
    "Browsers": ("browser",),
    "OS": ("operating system",),
    "Languages": ("language",),
}

# Weight metrics in preference order; first present column wins.
METRIC_PRIORITY = (
    "active users",
    "users",
    "total users",
    "sessions",
    "session(s) count",
    "engaged sessions",
    "event count",
    "views",
    "screen views",
)

DATE_COLUMNS = ("date", "session date", "session date (day of week)", "week of the month", "week of")


def normalise_header(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def _num(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_rows_from_csv(raw: bytes) -> list[dict[str, Any]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    # GA4 exports wrap the table in "# ..." comment preamble/footer lines and
    # blank rows; keep only real data lines so DictReader sees the true header.
    body = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not body:
        return []
    reader = csv.DictReader(StringIO("\n".join(body)))
    rows: list[dict[str, Any]] = []
    for row in reader:
        clean: dict[str, Any] = {}
        for key, value in row.items():
            if key is None:
                continue
            clean[normalise_header(key)] = value
        if any(str(v).strip() for v in clean.values() if v is not None):
            rows.append(clean)
    return rows


def _find_rows(parsed: Any, depth: int = 0) -> list[dict[str, Any]] | None:
    if depth > 3:
        return None
    if isinstance(parsed, list):
        dicts = [item for item in parsed if isinstance(item, dict)]
        return dicts or None
    if isinstance(parsed, dict):
        for value in parsed.values():
            found = _find_rows(value, depth + 1)
            if found:
                return found
    return None


def parse_rows_from_json(raw: bytes) -> list[dict[str, Any]] | None:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    rows = _find_rows(parsed)
    if not rows:
        return None
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({normalise_header(key): value for key, value in row.items()})
    return out


def _is_metric_header(header: str) -> bool:
    if "%" in header or "percent" in header or "rate" in header or "average" in header or "time" in header:
        return False
    return any(token in header for token in ("user", "session", "count", "event", "view", "total", "engagement"))


def _find_column(headers: set[str], aliases: tuple[str, ...]) -> str | None:
    """Locate a real column for a group: exact alias first, then substring."""
    for alias in aliases:
        if alias in headers:
            return alias
    for header in sorted(headers):
        if "%" in header or _is_metric_header(header):
            continue
        for alias in aliases:
            if alias in header:
                return header
    return None


def _pick_metric(headers: set[str]) -> str | None:
    candidates = [h for h in headers if _is_metric_header(h)]
    for metric in METRIC_PRIORITY:
        for header in candidates:
            if header == metric or metric in header:
                return header
    return candidates[0] if candidates else None


def _aggregate(rows: list[dict[str, Any]], dimension: str, metric: str | None) -> list[dict[str, Any]]:
    weights: dict[str, float] = {}
    for row in rows:
        label = str(row.get(dimension) or "").strip()
        if not label or label.lower() in {"(not set)", "(other)", "(none)"}:
            continue
        weight = _num(row.get(metric)) if metric else 1.0
        weights[label] = weights.get(label, 0.0) + (weight or 1.0)
    total = sum(weights.values()) or 1
    top = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:8]
    return [
        {"label": label, "value": int(round(value)), "share": round(value / total * 100, 1)}
        for label, value in top
    ]


def build_summary(
    file_rows: list[tuple[str, list[dict[str, Any]]]],
    *,
    source: str,
    synced_at: str,
) -> dict[str, Any]:
    """Combine parsed rows from one or more exports into the dashboard payload."""
    all_rows: list[dict[str, Any]] = []
    headers: set[str] = set()
    for rows in [rows for _, rows in file_rows if rows]:
        all_rows.extend(rows)
        for row in rows:
            headers.update(row.keys())

    if not all_rows:
        return {
            "data_available": False,
            "source": source,
            "synced_at": synced_at,
            "files": [name for name, _ in file_rows],
            "latest_file": file_rows[-1][0] if file_rows else "",
            "rows": 0,
            "stats": {},
            "insights": ["Exports were found but contained no parseable rows."],
            "groups": {},
            "range": {},
            "sample": [],
        }

    parsed_files = [(name, rows) for name, rows in file_rows if rows]
    all_headers: set[str] = set()
    for _, rows in parsed_files:
        for row in rows:
            all_headers.update(row.keys())

    metric = _pick_metric(all_headers)
    stats: dict[str, Any] = {"rows": len(all_rows)}
    # Per-metric total taken as the MAX single-file column sum (not a cross-file
    # sum) so overlapping dimensions across the 6 GA4 exports don't double-count
    # the same audience.
    numeric_headers = [
        header for header in all_headers if _is_metric_header(header)
    ][:12]
    for header in numeric_headers:
        sums = [sum(_num(row.get(header)) for row in rows) for _, rows in parsed_files]
        best = int(round(max(sums))) if sums else 0
        if best:
            stats[header.title()] = best

    groups: dict[str, list[dict[str, Any]]] = {}
    group_metric: dict[str, str] = {}
    for group_name, aliases in DIMENSION_GROUPS.items():
        column = _find_column(all_headers, aliases)
        if not column:
            continue
        # Pick the file whose report is dedicated to this dimension (highest
        # weighted distinct values) to avoid summing a repeated column, and use
        # that file's own best metric so shares reflect real sessions/users.
        best_agg: list[dict[str, Any]] = []
        best_score = -1.0
        best_metric: str | None = None
        for _, rows in parsed_files:
            file_headers: set[str] = set()
            for row in rows:
                file_headers.update(row.keys())
            file_metric = _pick_metric(file_headers)
            present = [row for row in rows if str(row.get(column) or "").strip()]
            if len(present) < 2:
                continue
            aggregated = _aggregate(rows, column, file_metric)
            score = sum(a["value"] for a in aggregated) + len(aggregated)
            if aggregated and score > best_score:
                best_score, best_agg, best_metric = score, aggregated, file_metric
        if best_agg:
            groups[group_name] = best_agg
            group_metric[group_name] = best_metric or ""

    dates: list[str] = []
    for header in all_headers:
        if header in DATE_COLUMNS or "date" == header:
            for row in all_rows:
                value = str(row.get(header) or "").strip()
                if value:
                    dates.append(value)
            if dates:
                break
    date_range = {"from": min(dates), "to": max(dates)} if dates else {}

    insights: list[str] = []
    if date_range:
        insights.append(f"Period: {date_range['from']} to {date_range['to']}")
    group_lead_word = {
        "Cities": "city", "Countries": "country", "Regions": "region", "Devices": "device",
        "Sources": "source", "Pages": "page", "Browsers": "browser", "OS": "OS", "Languages": "language",
    }
    for group_name in ("Cities", "Countries", "Devices", "Sources", "Pages"):
        top = groups.get(group_name) or []
        if top:
            lead = top[0]
            word = group_lead_word.get(group_name, group_name.lower())
            gmetric = group_metric.get(group_name) or ""
            unit = gmetric.title() if gmetric else "rows"
            insights.append(
                f"Top {word}: {lead['label']} - {lead['value']:,} {unit} ({lead['share']}%)"
            )
    insights.append(f"Processed {len(file_rows)} export file(s), {len(all_rows):,} rows.")

    return {
        "data_available": True,
        "source": source,
        "synced_at": synced_at,
        "files": [name for name, _ in file_rows],
        "latest_file": file_rows[-1][0] if file_rows else "",
        "rows": len(all_rows),
        "metric": metric or "",
        "stats": stats,
        "insights": insights,
        "groups": groups,
        "range": date_range,
        "sample": all_rows[:3],
    }


def files_signature(files: list[dict[str, Any]]) -> str:
    """Stable signature of name+updated pairs to detect new/changed exports."""
    parts = sorted(f"{entry.get('name')}|{entry.get('updated')}" for entry in files)
    return ";".join(parts)
