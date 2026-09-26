"""Event workbook parsing for the Kalisoft ``events list.xlsx`` file.

The real workbook is hand-maintained, so this parser is deliberately tolerant:

* three different event layouts (exhibition list, link + free-text list, and a
  tracker table with an ``Event name`` header);
* dates written as real Excel datetimes, ``Sat, Sep 5, 2026, 9:30 AM``,
  ``19-20-21 Feb, 2026``, ``15/01/2026 23:30`` or ``5, 6, 7, 8 FEBRUARY - 2026``;
* a contacts sheet whose rows are CSV fragments stored inside a single cell,
  sometimes with several phone numbers in one field;
* empty placeholder sheets, which are skipped instead of raising.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

MAX_TEXT = 8_000
MAX_TITLE = 220
MAX_SHORT = 400

_URL = re.compile(r"https?://[^\s<>\"'()\[\],]+", re.I)
_WEEKDAY_PREFIX = re.compile(
    r"^(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*\.?,?\s+", re.I
)
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", re.I)
_PHONE_CHARS = re.compile(r"^[\d+\s()-]{7,}$")

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# Ordered most-specific first. Each pattern is (day, month-name, year) or
# (day, month-number, year) after the named groups are applied.
_DATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 19-20-21 Feb, 2026 / 28 -30 January 2026 / 23 , 24 , 25 January 2026
    (
        re.compile(
            r"(\d{1,2})(?:\s*[-,/]\s*\d{1,2}){0,2}\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})",
            re.I,
        ),
        "dmy",
    ),
    # 9 April, 2026 / Mon, Dec 29, 2025
    (re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", re.I), "dmy"),
    # September 23, 2026 / Sep 4, 2026
    (re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.I), "mdy"),
    # 15/01/2026 or 15-01-2026
    (re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})"), "dmy_num"),
    # 5, 6, 7, 8 FEBRUARY - 2026
    (re.compile(r"([A-Za-z]{3,9})\.?\s*[-\u2013]\s*(\d{4})", re.I), "month_year"),
    # Year-less rows such as "sept 24 -25 Denver colorado"
    (re.compile(r"(\d{1,2})\s*[-\u2013]\s*(\d{1,2})\s+([A-Za-z]{3,9})", re.I), "dmy_noyear"),
    (
        re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:\s*[-\u2013]\s*\d{1,2})?\b", re.I),
        "mdy_noyear",
    ),
    (re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\b", re.I), "dmy_noyear"),
]

_YEAR_ROLLOVER_DAYS = 180


def _default_year(month: int, day: int) -> int:
    """Pick the year for a date the workbook omitted.

    Rows such as ``sept 24 -25 Denver colorado`` are always forward-looking, so
    a date that already passed this year belongs to the next one.
    """
    today = datetime.utcnow()
    year = today.year
    candidate = _safe_datetime(year, month, day)
    if candidate and (today.date() - candidate.date()).days > _YEAR_ROLLOVER_DAYS:
        year += 1
    return year


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y, %I:%M %p").lstrip("0")
    return re.sub(r"[ \t\u00a0]+", " ", str(value)).strip()


def _clip(value: str, limit: int = MAX_TEXT) -> str:
    value = re.sub(r"\n{3,}", "\n\n", (value or "").strip())
    return value[:limit]


def first_url(value: Any) -> str:
    """Return the first http(s) URL in a cell, or an empty string."""
    match = _URL.search(_text(value))
    return match.group(0).rstrip(".,;") if match else ""


def _url_title(url: str) -> str:
    host = urlparse(url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    return host.split("/")[0] or "Event"


def _month_number(name: str) -> int:
    return _MONTHS.get(name.strip().lower()[:9].rstrip("."), 0)


def _safe_datetime(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0
) -> datetime | None:
    try:
        return datetime(year, month, day, min(hour, 23), min(minute, 59))
    except ValueError:
        return None


def _date_parts(kind: str, groups: tuple[str, ...]) -> tuple[int | None, int, int] | None:
    """Map matched groups to ``(year, month_number, day)`` for one pattern kind.

    ``dmy_noyear`` covers both ``sept 24 -25`` (three groups) and ``24 sept``
    (two groups), so its month is always the trailing group. ``None`` is
    returned when the month name is not recognised, so callers can skip.
    """
    if kind == "dmy":
        day, month, year = groups
        month_number = _month_number(month)
    elif kind == "mdy":
        month, day, year = groups
        month_number = _month_number(month)
    elif kind == "dmy_num":
        day, month, year = groups
        month_number = int(month)
    elif kind == "month_year":
        month, year = groups
        day, month_number = "1", _month_number(month)
    elif kind == "mdy_noyear":
        month, day = groups
        year, month_number = None, _month_number(month)
    else:  # dmy_noyear
        day, month = groups[0], groups[-1]
        year, month_number = None, _month_number(month)
    if not month_number:
        return None
    return (int(year) if year is not None else None), month_number, int(day)


def _time_parts(groups: tuple[str, ...]) -> tuple[int, int, str]:
    """Unpack ``H:MM`` with an optional am/pm suffix into hour/minute/meridiem."""
    hour, minute, *rest = groups
    return int(hour), int(minute), (rest[0] if rest else "")


def parse_event_when(value: Any) -> dict[str, Any]:
    """Extract start/end datetimes, a display string and a location hint.

    ``value`` may be a datetime, or free text such as
    ``"9 April, 2026 - 11 April, 2026\\n\\nPIECC, Moshi, Pune"``.
    """
    if isinstance(value, datetime):
        return {
            "starts_at": value.replace(second=0, microsecond=0),
            "ends_at": None,
            "when_text": value.strftime("%a, %d %b %Y, %I:%M %p").lstrip("0"),
            "location": "",
        }

    raw = _text(value)
    if not raw:
        return {"starts_at": None, "ends_at": None, "when_text": "", "location": ""}

    location = ""
    if "\n" in raw:
        head, _, tail = raw.partition("\n")
        head = head.strip().rstrip(",")
        tail = tail.strip()
        if tail:
            location = _clip(re.split(r"\n\s*\n", tail)[0], MAX_SHORT)
        date_part = head
    else:
        date_part = raw

    date_part = _WEEKDAY_PREFIX.sub("", date_part).strip()
    found: list[datetime] = []
    for pattern, kind in _DATE_PATTERNS:
        for match in pattern.finditer(date_part):
            parts = _date_parts(kind, match.groups())
            if parts is None:
                continue
            year, month_number, day = parts
            if year is None:
                year = _default_year(month_number, day)
            parsed = _safe_datetime(year, month_number, day)
            if parsed and parsed not in found:
                found.append(parsed)
        if found:
            break

    if not found:
        return {
            "starts_at": None,
            "ends_at": None,
            "when_text": raw[:MAX_SHORT],
            "location": location,
        }

    starts_at = found[0]
    times = _TIME.findall(date_part)
    if times:
        starts_at = _apply_time(starts_at, *_time_parts(times[0]))
    if len(found) > 1:
        ends_at = found[1]
        if len(times) > 1:
            ends_at = _apply_time(ends_at, *_time_parts(times[1]))
    elif len(times) > 1:
        # A single date with a time range, e.g. "10:00 - 18:00" on one day.
        ends_at = _apply_time(starts_at, *_time_parts(times[1]))
    else:
        ends_at = None
    if ends_at is not None and ends_at <= starts_at:
        ends_at = starts_at + timedelta(days=1)

    return {
        "starts_at": starts_at,
        "ends_at": ends_at,
        "when_text": date_part[:MAX_SHORT],
        "location": location,
    }


def _apply_time(value: datetime, hour: int, minute: int, meridiem: str) -> datetime:
    meridiem = (meridiem or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return value.replace(hour=min(hour, 23), minute=min(minute, 59))


def detect_mode(*values: str) -> str:
    text = " ".join(v for v in values if v).lower()
    online = any(token in text for token in ("online", "webinar", "virtual", "zoom", "teams"))
    physical = any(
        token in text
        for token in (
            "in-person",
            "in person",
            "on-site",
            "onsite",
            "exhibition",
            "pune",
            "mumbai",
            "belgrade",
        )
    )
    if online and physical:
        return "hybrid"
    if online:
        return "online"
    if physical:
        return "in_person"
    return "unknown"


def normalise_phone(value: Any) -> list[str]:
    """Return E.164-ish phone numbers, splitting multi-number cells."""
    text = _text(value)
    if not text:
        return []
    numbers: list[str] = []
    for chunk in re.split(r"[,;/]| or ", text):
        if not _PHONE_CHARS.match(chunk.strip()):
            continue
        digits = re.sub(r"\D", "", chunk)
        if len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        if len(digits) == 10 and digits[0] in "6789":
            digits = f"91{digits}"
        if 10 <= len(digits) <= 15 and digits not in numbers:
            numbers.append(digits)
    return numbers


def _clean_title(value: str) -> str:
    title = re.sub(r"\s+", " ", (value or "").strip())
    title = re.sub(r"^event by\s+", "", title, flags=re.I)
    if not title or _URL.search(title) or len(title) > MAX_TITLE:
        return ""
    return title.strip(" -–—|:,")


def _event(**kwargs: Any) -> dict[str, Any]:
    record = {
        "title": "",
        "event_url": "",
        "starts_at": None,
        "ends_at": None,
        "when_text": "",
        "location": "",
        "mode": "unknown",
        "organiser": "",
        "attendance": "",
        "about": "",
        "todo": "",
        "source_sheet": "",
        "source_row": 0,
    }
    record.update({key: value for key, value in kwargs.items() if value not in (None, "")})
    if not record["mode"] or record["mode"] == "unknown":
        record["mode"] = detect_mode(
            str(record.get("when_text", "")),
            str(record.get("location", "")),
            str(record.get("about", ""))[:400],
        )
    if not record["title"]:
        record["title"] = _url_title(str(record["event_url"])) or "Untitled event"
    return record


def _parse_tracker_sheet(sheet_name: str, rows: list[list[Any]]) -> list[dict[str, Any]]:
    """Parse a table whose header row contains ``Event name``."""
    header_index = -1
    headers: list[str] = []
    for index, row in enumerate(rows):
        labels = [_text(cell).strip().lower() for cell in row]
        if any(label.startswith("event name") for label in labels):
            header_index = index
            headers = labels
            break
    if header_index < 0:
        return []

    def column(*names: str) -> int:
        for name in names:
            for position, label in enumerate(headers):
                if label.startswith(name):
                    return position
        return -1

    idx_name = column("event name")
    idx_organiser = column("arranged by", "organiser", "organizer")
    idx_time = column("time", "date")
    idx_link = column("meeting link", "event link", "link")
    idx_attendance = column("attendance")
    idx_mode = column("meeting mode", "mode")
    idx_about = column("about", "description")
    idx_location = column("location", "venue")

    events: list[dict[str, Any]] = []
    for offset, row in enumerate(rows[header_index + 1 :], start=header_index + 2):

        def cell(index: int) -> Any:
            return row[index] if 0 <= index < len(row) else None

        title = _clean_title(_text(cell(idx_name)))
        when = parse_event_when(cell(idx_time))
        location = _clip(_text(cell(idx_location)), MAX_SHORT) or when["location"]
        about = _clip(_text(cell(idx_about)))
        link = first_url(cell(idx_link)) or first_url(_text(cell(idx_time))) or first_url(about)
        if not title and not link and not when["starts_at"]:
            continue
        events.append(
            _event(
                title=title or _url_title(link),
                event_url=link,
                starts_at=when["starts_at"],
                ends_at=when["ends_at"],
                when_text=when["when_text"] or _clip(_text(cell(idx_time)), MAX_SHORT),
                location=location,
                mode=detect_mode(_text(cell(idx_mode)), location, about[:400]),
                organiser=_clip(_text(cell(idx_organiser)).replace("Event by", "", 1), 255),
                attendance=_clip(_text(cell(idx_attendance)), 128),
                about=about,
                source_sheet=sheet_name,
                source_row=offset,
            )
        )
    return events


def _parse_exhibition_sheet(sheet_name: str, rows: list[list[Any]]) -> list[dict[str, Any]]:
    """Parse the ``Events / Date and Location / About / To do list`` layout."""
    header_index = -1
    for index, row in enumerate(rows):
        labels = [_text(cell).strip().lower() for cell in row]
        if labels and labels[0].startswith("event") and any("date" in label for label in labels):
            header_index = index
            break
    if header_index < 0:
        return []

    events: list[dict[str, Any]] = []
    for offset, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        link_cell = _text(row[0] if len(row) > 0 else "")
        when_cell = row[1] if len(row) > 1 else None
        about_cell = row[2] if len(row) > 2 else None
        todo_cell = row[3] if len(row) > 3 else None
        if not any(_text(cell) for cell in (link_cell, when_cell, about_cell, todo_cell)):
            continue

        link = first_url(link_cell) or first_url(about_cell)
        about = _clip(_text(about_cell)) if not first_url(about_cell) else ""
        title = _clean_title(_text(about_cell)) or _clean_title(link_cell)
        if not title:
            title = _url_title(link)
        if about and len(about) <= MAX_TITLE and "\n" not in about and not title:
            title = about
        when = parse_event_when(when_cell)
        events.append(
            _event(
                title=title,
                event_url=link,
                starts_at=when["starts_at"],
                ends_at=when["ends_at"],
                when_text=when["when_text"],
                location=when["location"],
                about=about or _clip(_text(about_cell)),
                todo=_clip(_text(todo_cell)),
                source_sheet=sheet_name,
                source_row=offset,
            )
        )
    return events


_KEYED = re.compile(r"^(date|dates|time|venue|location|place|mode|audience)\s*:", re.I)
_RELATIVE = re.compile(
    r"^(today|tomorrow|tonight|next week|this (?:week|month)|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\b",
    re.I,
)


def _line_start(line: str) -> datetime | None:
    """Return a datetime if a free-text line carries a real calendar date."""
    cleaned = _WEEKDAY_PREFIX.sub("", line).strip()
    for pattern, kind in _DATE_PATTERNS:
        match = pattern.search(cleaned)
        if not match:
            continue
        parts = _date_parts(kind, match.groups())
        if parts is None:
            continue
        year, month_number, day = parts
        if year is None:
            year = _default_year(month_number, day)
        found = _safe_datetime(year, month_number, day)
        if found:
            return found
    return None


def _split_keyed(body: str) -> list[str]:
    """Split glued ``Date: ... Location: ...`` fragments into separate lines."""
    spaced = re.sub(
        r"(?<=[a-z0-9)])(?=(?:Date|Location|Venue|Place|Mode|Audience|Time)\s*:)", "\n", body
    )
    return [line.strip() for line in spaced.split("\n") if line.strip()]


def _parse_link_sheet(sheet_name: str, rows: list[list[Any]]) -> list[dict[str, Any]]:
    """Parse sheets that pair a link column with a free-text description.

    The description looks like::

        Today, 4:30 PM
        Next Level AI - 2-Day Advanced Claude & Agentic Thinking
        Event by CoLab Lisbon
        Sat, Aug 22, 2026, 4:30 PM - 9:30 PM (your local time)
        Avenida Infante Dom Henrique 143, Beato, Lisboa
    """
    events: list[dict[str, Any]] = []
    for offset, row in enumerate(rows, start=1):
        cells = [_text(cell) for cell in row]
        if not any(cells):
            continue
        link = next((first_url(cell) for cell in cells if first_url(cell)), "")
        body = next((cell for cell in cells if cell and not first_url(cell)), "")
        if not link and not body:
            continue
        if not link and not re.search(r"\d{4}", body):
            continue

        title = ""
        organiser = ""
        location = ""
        date_lines: list[str] = []
        about_lines: list[str] = []
        for line in _split_keyed(body):
            if _line_start(line):
                date_lines.append(line)
                continue
            if _RELATIVE.match(line) and not date_lines:
                continue
            if not title and not location and not date_lines and not _KEYED.match(line):
                candidate = _clean_title(line)
                if candidate:
                    title = candidate
                    continue
            if line.lower().startswith("event by"):
                organiser = re.sub(r"^event by\s*", "", line, flags=re.I)[:255]
                continue
            keyed = _KEYED.match(line)
            value = line[keyed.end() :].strip(" :-") if keyed else line
            if keyed and keyed.group(1).lower() in {"date", "dates", "time"}:
                date_lines.append(value)
            elif keyed and keyed.group(1).lower() in {"venue", "location", "place", "mode"}:
                location = _clip(value, MAX_SHORT)
            elif not location:
                location = _clip(value, MAX_SHORT)
            else:
                about_lines.append(line)

        when = parse_event_when(" | ".join(date_lines))
        location = location or when["location"]
        if not link and not date_lines and not location:
            # Section titles such as "Event 2026" are not events.
            continue
        mode = detect_mode(location, " ".join(about_lines)[:400])
        if mode == "unknown" and location and not _KEYED.match(location):
            mode = "in_person"
        events.append(
            _event(
                title=title,
                event_url=link,
                starts_at=when["starts_at"],
                ends_at=when["ends_at"],
                when_text=when["when_text"],
                location=location,
                mode=mode,
                organiser=organiser,
                about=_clip("\n".join(about_lines)),
                source_sheet=sheet_name,
                source_row=offset,
            )
        )
    return events


def _parse_contacts_sheet(rows: list[list[Any]]) -> list[dict[str, Any]]:
    """Parse a sheet whose rows are CSV fragments (often inside one cell)."""
    contacts: list[dict[str, Any]] = []
    for offset, row in enumerate(rows, start=1):
        for cell in row:
            line = _text(cell)
            if not line or "," not in line:
                continue
            parts = [part.strip() for part in next(csv.reader([line]))]
            if len(parts) < 2:
                continue
            lowered = [part.lower() for part in parts]
            if "company" in lowered and "phone" in lowered:
                continue
            company = parts[1] if len(parts) > 1 else ""
            name = parts[2] if len(parts) > 2 else ""
            if not name and not company:
                continue
            position = 3
            phones: list[str] = []
            while position < len(parts) and _PHONE_CHARS.match(parts[position]):
                phones.extend(normalise_phone(parts[position]))
                position += 1
            notes = ", ".join(part for part in parts[position:] if part)
            for phone in phones:
                contacts.append(
                    {
                        "company": _clip(company, 255),
                        "name": _clip(name, 255),
                        "phone": phone,
                        "notes": _clip(notes),
                        "source_sheet": "contacts",
                        "source_row": offset,
                    }
                )
    return contacts


def _is_contacts_sheet(rows: list[list[Any]]) -> bool:
    for row in rows[:60]:
        for cell in row:
            text = _text(cell).lower()
            if "," in text and "phone" in text and ("company" in text or "category" in text):
                return True
    return False


def parse_workbook(raw: bytes) -> dict[str, list[dict[str, Any]]]:
    """Parse the workbook bytes into ``{"events": [...], "contacts": [...]}``."""
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    events: list[dict[str, Any]] = []
    contacts: list[dict[str, Any]] = []
    parsed_sheets: list[str] = []

    for sheet in workbook.worksheets:
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        if not any(any(_text(cell) for cell in row) for row in rows):
            continue
        if _is_contacts_sheet(rows):
            found = _parse_contacts_sheet(rows)
            if found:
                contacts.extend(found)
                parsed_sheets.append(sheet.title)
            continue
        found = (
            _parse_tracker_sheet(sheet.title, rows)
            or _parse_exhibition_sheet(sheet.title, rows)
            or _parse_link_sheet(sheet.title, rows)
        )
        if found:
            events.extend(found)
            parsed_sheets.append(sheet.title)

    return {"events": events, "contacts": contacts, "sheets": parsed_sheets}
