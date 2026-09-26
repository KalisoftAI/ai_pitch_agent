"""Events dashboard: workbook import, showcase and WhatsApp scheduling.

The event workbook is maintained by hand in Excel, so parsing lives in
``event_importer`` and this module owns persistence, tenant scoping, preview and
audited dispatch. Nothing is ever sent implicitly: messages are queued with an
optional schedule time and only leave the app through the explicit send
endpoints (or the ``events_whatsapp_due`` scheduler task).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..event_importer import parse_workbook
from ..governance.audit import log_event
from ..models import Event, EventMessage, EventRecipient, User
from ..schemas import (
    EventImportOut,
    EventMessageListOut,
    EventOut,
    EventRecipientOut,
    EventScheduleIn,
    EventScheduleOut,
    EventSendResultOut,
    EventSummaryOut,
    EventTemplateOut,
)
from ..security import get_current_user
from ..templating import render_optional, variables_used
from ..wechaty import WechatyGateway

router = APIRouter(prefix="/events", tags=["events"])

STATUS_UPCOMING = "upcoming"
STATUS_PAST = "past"
STATUS_UNSCHEDULED = "unscheduled"

DEFAULT_EVENT_TEMPLATE = (
    "Hello {{name}}{{company_suffix}},\n\n"
    "We will be at {{event_title}}{{event_dates}}.\n"
    "{{where_lines}}\n\n"
    "We would love to meet you and show how Kalisoft AI can help {{company}}. "
    "Please let us know a convenient time.\n\n"
    "— Team Kalisoft AI"
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _utcnow() -> datetime:
    return datetime.utcnow()


def _fingerprint(title: str, event_url: str, starts_at: datetime | None, organiser: str) -> str:
    """Stable per-event key so re-importing updates instead of duplicating."""
    if event_url:
        key = re.sub(r"[?#].*$", "", event_url.strip().lower()).rstrip("/")
    else:
        when = starts_at.strftime("%Y-%m-%d") if starts_at else "na"
        key = f"{title.strip().lower()}|{when}|{organiser.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:64]


def _event_status(event: Event) -> str:
    if not event.starts_at:
        return STATUS_UNSCHEDULED
    end = event.ends_at or event.starts_at
    return STATUS_PAST if end < _utcnow() else STATUS_UPCOMING


def _refresh_statuses(db: Session, user_id: int) -> None:
    changed = False
    for event in db.query(Event).filter(Event.user_id == user_id).all():
        status = _event_status(event)
        if event.status != status:
            event.status = status
            changed = True
    if changed:
        db.commit()


def _sort_key(event: Event) -> tuple[int, float, str]:
    """Upcoming first (soonest first), then unscheduled, then most recent past."""
    starts = event.starts_at.timestamp() if event.starts_at else 0.0
    if event.status == STATUS_PAST:
        return (2, -starts, event.title.lower())
    if event.status == STATUS_UNSCHEDULED:
        return (1, 0.0, event.title.lower())
    return (0, starts, event.title.lower())


def _format_when(event: Event) -> str:
    if event.starts_at and event.ends_at and event.starts_at.date() != event.ends_at.date():
        return f" ({event.starts_at.strftime('%d %b %Y, %I:%M %p')} to {event.ends_at.strftime('%d %b %Y, %I:%M %p')})"
    if event.starts_at:
        return f" ({event.starts_at.strftime('%a, %d %b %Y, %I:%M %p')})"
    if event.when_text:
        return f" ({event.when_text})"
    return ""


def event_context(event: Event, recipient: EventRecipient | None = None) -> dict[str, str]:
    """Template variables available for event outreach.

    Values fall back to safe wording so a queued message never ships a raw
    ``{{placeholder}}`` to a customer.
    """
    company = (recipient.company if recipient else "") or ""
    location = event.location or ("Online" if event.mode == "online" else "")
    where_bits = []
    if location:
        where_bits.append(f"📍 Where: {location}")
    if event.event_url:
        where_bits.append(f"🔗 Details: {event.event_url}")
    return {
        "event_title": event.title or "the event",
        "event_dates": _format_when(event),
        "event_when": event.when_text
        or (event.starts_at.isoformat() if event.starts_at else "soon"),
        "event_where": location or "the venue shared on the event page",
        "event_url": event.event_url or "the event page",
        "event_mode": event.mode,
        "event_organiser": event.organiser or "the organiser",
        "event_attendance": event.attendance,
        "event_todo": event.todo,
        "name": (recipient.name if recipient else "") or "there",
        "company": company or "your organisation",
        "company_suffix": f" from {company}" if company else "",
        "phone": (recipient.phone if recipient else "") or "",
        "where_lines": "\n".join(where_bits),
    }


def render_message(template: str, context: dict[str, str]) -> str:
    """Render a template and tidy the whitespace left by empty values."""
    body = render_optional(template, context)
    lines = [line.rstrip() for line in body.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line.strip())).strip()


def _resolve_workbook(source_path: str) -> Path:
    """Resolve a workbook path inside the local data directory only."""
    base = Path(settings.EVENTS_LOCAL_DIR).resolve()
    candidate = (
        (base / source_path).resolve()
        if source_path
        else (base / settings.EVENTS_WORKBOOK_NAME).resolve()
    )
    try:
        candidate.relative_to(base)
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=400, detail="Workbook path must stay inside the data directory"
        ) from exc
    if not candidate.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"{candidate.name} not found. Upload the workbook from the Events tab.",
        )
    return candidate


def _validate_workbook(raw: bytes) -> dict:
    if not raw:
        raise HTTPException(status_code=400, detail="Workbook is empty")
    if len(raw) > settings.MAX_REQUEST_BYTES * 5:
        raise HTTPException(status_code=413, detail="Workbook is too large")
    if not raw[:2] == b"PK":
        raise HTTPException(status_code=400, detail="Only .xlsx workbooks are supported")
    try:
        return parse_workbook(raw)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced as 422
        raise HTTPException(status_code=422, detail=f"Could not read workbook: {exc}") from exc


def _get_event(db: Session, user: User, event_id: int) -> Event:
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == user.id).one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _unknown_variables(template: str, context: dict[str, str]) -> list[str]:
    """Placeholders the template uses that the context cannot supply at all."""
    return sorted(name for name in variables_used(template) if name not in context)


def dispatch_event_message(db: Session, message: EventMessage) -> EventSendResultOut:
    """Send a single queued message through the audited gateway path."""
    if message.status == "sent":
        return EventSendResultOut(
            message_id=message.id, ok=True, status="sent", phone=message.phone
        )
    if message.status == "cancelled":
        raise HTTPException(status_code=409, detail="Message was cancelled")
    if not settings.WHATSAPP_ENABLED:
        raise HTTPException(status_code=503, detail="WhatsApp channel is disabled")

    gateway = WechatyGateway()
    try:
        gateway.send_text(message.phone, message.body)
    except Exception as exc:  # noqa: BLE001 - recorded on the row
        message.status = "failed"
        message.error = str(exc)[:512]
        db.commit()
        return EventSendResultOut(
            message_id=message.id,
            ok=False,
            status="failed",
            phone=message.phone,
            error=message.error,
        )

    message.status = "sent"
    message.sent_at = _utcnow()
    message.error = ""
    db.commit()
    return EventSendResultOut(message_id=message.id, ok=True, status="sent", phone=message.phone)


def dispatch_due_event_messages(db: Session, user_id: int, limit: int = 50) -> dict[str, int]:
    """Send every queued message whose schedule time has passed."""
    if not settings.WHATSAPP_ENABLED:
        return {"sent": 0, "failed": 0, "skipped": 0}
    now = _utcnow()
    due = (
        db.query(EventMessage)
        .filter(
            EventMessage.user_id == user_id,
            EventMessage.status == "queued",
            EventMessage.scheduled_at.isnot(None),
            EventMessage.scheduled_at <= now,
        )
        .order_by(EventMessage.scheduled_at.asc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    sent = failed = 0
    for message in due:
        outcome = dispatch_event_message(db, message)
        if outcome.ok:
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "failed": failed, "skipped": 0}


# --------------------------------------------------------------------------- #
# routes
# --------------------------------------------------------------------------- #
@router.get("/summary", response_model=EventSummaryOut)
def events_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _refresh_statuses(db, user.id)
    events = db.query(Event).filter(Event.user_id == user.id).all()
    now = _utcnow()
    soon = now + timedelta(days=30)
    counts = {"online": 0, "in_person": 0, "hybrid": 0, "upcoming": 0, "past": 0, "unscheduled": 0}
    for event in events:
        counts[event.mode] = counts.get(event.mode, 0) + 1
        counts[event.status] = counts.get(event.status, 0) + 1
    messages = (
        db.query(EventMessage.status, EventMessage.id).filter(EventMessage.user_id == user.id).all()
    )
    message_counts: dict[str, int] = {}
    for status, _ in messages:
        message_counts[status] = message_counts.get(status, 0) + 1
    latest = (
        db.query(Event).filter(Event.user_id == user.id).order_by(Event.updated_at.desc()).first()
    )
    return EventSummaryOut(
        events=len(events),
        upcoming=counts.get(STATUS_UPCOMING, 0),
        next_30_days=sum(
            1 for event in events if event.starts_at and now <= event.starts_at <= soon
        ),
        past=counts.get(STATUS_PAST, 0),
        online=counts.get("online", 0),
        in_person=counts.get("in_person", 0),
        hybrid=counts.get("hybrid", 0),
        unscheduled=counts.get(STATUS_UNSCHEDULED, 0),
        recipients=db.query(EventRecipient).filter(EventRecipient.user_id == user.id).count(),
        queued_messages=message_counts.get("queued", 0),
        sent_messages=message_counts.get("sent", 0),
        failed_messages=message_counts.get("failed", 0),
        last_imported_at=latest.updated_at if latest else None,
    )


@router.get("", response_model=list[EventOut])
def list_events(
    q: str = Query(default="", max_length=120),
    status: str = Query(default="", max_length=32),
    mode: str = Query(default="", max_length=32),
    upcoming_only: bool = False,
    order: str = Query(default="upcoming", pattern="^(upcoming|date|recent)$"),
    limit: int = Query(default=200, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _refresh_statuses(db, user.id)
    query = db.query(Event).filter(Event.user_id == user.id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            Event.title.ilike(like)
            | Event.organiser.ilike(like)
            | Event.location.ilike(like)
            | Event.when_text.ilike(like)
        )
    if status:
        query = query.filter(Event.status == status)
    if mode:
        query = query.filter(Event.mode == mode)
    if upcoming_only:
        query = query.filter(Event.status == STATUS_UPCOMING)
    events = query.all()
    if order == "date":
        events.sort(
            key=lambda event: (
                event.starts_at is None,
                event.starts_at or datetime.max,
                event.title,
            )
        )
    elif order == "recent":
        events.sort(key=lambda event: event.created_at, reverse=True)
    else:
        events.sort(key=_sort_key)
    return events[:limit]


@router.get("/recipients", response_model=list[EventRecipientOut])
def list_recipients(
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=200, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(EventRecipient).filter(EventRecipient.user_id == user.id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            EventRecipient.name.ilike(like)
            | EventRecipient.company.ilike(like)
            | EventRecipient.phone.ilike(like)
            | EventRecipient.notes.ilike(like)
        )
    return (
        query.order_by(EventRecipient.company.asc(), EventRecipient.name.asc()).limit(limit).all()
    )


@router.post("/import", response_model=EventImportOut)
async def import_workbook(
    request: Request,
    file: UploadFile | None = File(default=None),
    source_path: str = Form(default=""),
    include_contacts: bool = Form(default=True),
    include_events: bool = Form(default=True),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if file is not None and file.filename:
        raw = await file.read()
        source = file.filename
    else:
        path = _resolve_workbook(source_path)
        raw = path.read_bytes()
        source = path.name
    parsed = _validate_workbook(raw)

    now = _utcnow()
    events_imported = events_updated = 0
    if include_events:
        seen: dict[str, Event] = {}
        for record in parsed["events"]:
            fingerprint = _fingerprint(
                record.get("title", ""),
                record.get("event_url", ""),
                record.get("starts_at"),
                record.get("organiser", ""),
            )
            row = seen.get(fingerprint)
            if row is None:
                row = (
                    db.query(Event)
                    .filter(Event.user_id == user.id, Event.fingerprint == fingerprint)
                    .one_or_none()
                )
            if row is None:
                row = Event(user_id=user.id, fingerprint=fingerprint)
                db.add(row)
                seen[fingerprint] = row
                events_imported += 1
            else:
                events_updated += 1
            for field in (
                "title",
                "event_url",
                "starts_at",
                "ends_at",
                "when_text",
                "location",
                "mode",
                "organiser",
                "attendance",
                "about",
                "todo",
                "source_sheet",
                "source_row",
            ):
                setattr(
                    row,
                    field,
                    record.get(field, "") or (None if field in {"starts_at", "ends_at"} else ""),
                )
            row.title = row.title[:255]
            row.status = _event_status(row)
            row.updated_at = now

    contacts_imported = contacts_updated = 0
    if include_contacts:
        seen_contacts: dict[str, EventRecipient] = {}
        for record in parsed["contacts"]:
            phone = record.get("phone", "")
            row = seen_contacts.get(phone)
            if row is None:
                row = (
                    db.query(EventRecipient)
                    .filter(EventRecipient.user_id == user.id, EventRecipient.phone == phone)
                    .one_or_none()
                )
            if row is None:
                row = EventRecipient(user_id=user.id, phone=phone)
                db.add(row)
                seen_contacts[phone] = row
                contacts_imported += 1
            else:
                contacts_updated += 1
            row.name = (record.get("name") or "")[:255]
            row.company = (record.get("company") or "")[:255]
            row.notes = record.get("notes") or ""
            row.source_sheet = record.get("source_sheet", "")[:64]
            row.source_row = int(record.get("source_row") or 0)

    db.commit()

    log_event(
        db,
        action="event.import",
        actor_user_id=user.id,
        resource_type="event_workbook",
        resource_id=source[:128],
        ip_address=request.client.host if request.client else "",
        detail={
            "events_imported": events_imported,
            "events_updated": events_updated,
            "contacts_imported": contacts_imported,
            "contacts_updated": contacts_updated,
            "sheets": parsed["sheets"],
        },
        commit=True,
    )
    return EventImportOut(
        events_imported=events_imported,
        events_updated=events_updated,
        contacts_imported=contacts_imported,
        contacts_updated=contacts_updated,
        sheets=parsed["sheets"],
        source=source,
    )


@router.get("/messages/all", response_model=EventMessageListOut)
def list_event_messages(
    event_id: int | None = Query(default=None),
    status: str = Query(default="", max_length=32),
    limit: int = Query(default=100, ge=1, le=300),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(EventMessage).filter(EventMessage.user_id == user.id)
    if event_id:
        query = query.filter(EventMessage.event_id == event_id)
    if status:
        query = query.filter(EventMessage.status == status)
    items = (
        query.order_by(EventMessage.created_at.desc(), EventMessage.id.desc()).limit(limit).all()
    )
    counts: dict[str, int] = {}
    for (status_value,) in (
        db.query(EventMessage.status).filter(EventMessage.user_id == user.id).all()
    ):
        counts[status_value] = counts.get(status_value, 0) + 1
    return EventMessageListOut(items=items, counts=counts)


@router.post("/messages/{message_id}/send", response_model=EventSendResultOut)
def send_event_message(
    message_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    message = (
        db.query(EventMessage)
        .filter(EventMessage.id == message_id, EventMessage.user_id == user.id)
        .one_or_none()
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Queued message not found")
    if message.status == "queued" and message.scheduled_at and message.scheduled_at > _utcnow():
        raise HTTPException(
            status_code=409,
            detail=f"Message is scheduled for {message.scheduled_at.isoformat()} UTC. Cancel it or use send-due.",
        )
    outcome = dispatch_event_message(db, message)
    log_event(
        db,
        action="event.send",
        actor_user_id=user.id,
        resource_type="event_message",
        resource_id=str(message.id),
        status="success" if outcome.ok else "failure",
        ip_address=request.client.host if request.client else "",
        detail={"ok": outcome.ok, "status": outcome.status},
        commit=True,
    )
    return outcome


@router.post("/messages/{message_id}/cancel")
def cancel_event_message(
    message_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    message = (
        db.query(EventMessage)
        .filter(EventMessage.id == message_id, EventMessage.user_id == user.id)
        .one_or_none()
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Queued message not found")
    if message.status == "sent":
        raise HTTPException(status_code=409, detail="Message was already sent")
    message.status = "cancelled"
    db.commit()
    return {"ok": True, "id": message.id, "status": "cancelled"}


@router.post("/messages/send-due")
def send_due_event_messages(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.WHATSAPP_ENABLED:
        raise HTTPException(status_code=503, detail="WhatsApp channel is disabled")
    outcome = dispatch_due_event_messages(db, user.id, limit=limit)
    log_event(
        db,
        action="event.send_due",
        actor_user_id=user.id,
        resource_type="event_message",
        resource_id="due",
        ip_address=request.client.host if request.client else "",
        detail=outcome,
        commit=True,
    )
    return outcome


@router.get("/message-template-default")
def default_message_template(user: User = Depends(get_current_user)):
    return {
        "template": DEFAULT_EVENT_TEMPLATE,
        "variables": sorted(variables_used(DEFAULT_EVENT_TEMPLATE)),
    }


@router.get("/{event_id}", response_model=EventOut)
def event_detail(
    event_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_event(db, user, event_id)


@router.get("/{event_id}/message-template", response_model=EventTemplateOut)
def event_message_template(
    event_id: int,
    recipient_id: int | None = Query(default=None),
    template: str = Query(default="", max_length=4_096),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = _get_event(db, user, event_id)
    recipient = None
    if recipient_id:
        recipient = (
            db.query(EventRecipient)
            .filter(EventRecipient.id == recipient_id, EventRecipient.user_id == user.id)
            .one_or_none()
        )
        if recipient is None:
            raise HTTPException(status_code=404, detail="Recipient not found")
    body = template or DEFAULT_EVENT_TEMPLATE
    context = event_context(event, recipient)
    return EventTemplateOut(
        event_id=event.id,
        template=body,
        variables=sorted(variables_used(body)),
        preview=render_message(body, context),
        preview_name=context["name"],
        recipient_count=db.query(EventRecipient).filter(EventRecipient.user_id == user.id).count(),
    )


@router.post("/{event_id}/schedule", response_model=EventScheduleOut)
def schedule_event_messages(
    event_id: int,
    payload: EventScheduleIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = _get_event(db, user, event_id)
    template = payload.template.strip()
    if not template:
        raise HTTPException(status_code=422, detail="Message template cannot be empty")
    if len(template) > 4_096:
        raise HTTPException(
            status_code=422, detail="WhatsApp messages are limited to 4096 characters"
        )

    recipients = (
        db.query(EventRecipient)
        .filter(
            EventRecipient.user_id == user.id, EventRecipient.id.in_(payload.recipient_ids or [0])
        )
        .all()
        if payload.recipient_ids
        else []
    )
    if not payload.preview_only and not recipients:
        raise HTTPException(status_code=422, detail="Select at least one recipient")

    scheduled_at = payload.scheduled_at
    if scheduled_at is not None and scheduled_at.tzinfo is not None:
        # Times are persisted as naive UTC, so an aware input is normalised once.
        scheduled_at = scheduled_at.astimezone(timezone.utc).replace(tzinfo=None)
    elif scheduled_at is None:
        scheduled_at = _utcnow() + timedelta(minutes=settings.EVENTS_DEFAULT_LEAD_MINUTES)

    first = recipients[0] if recipients else None
    context = event_context(event, first)
    unknown = _unknown_variables(template, context)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown template variable(s): {', '.join(unknown)}",
        )

    queued = 0
    message_ids: list[int] = []
    if not payload.preview_only:
        existing = {
            row.recipient_id
            for row in db.query(EventMessage)
            .filter(
                EventMessage.user_id == user.id,
                EventMessage.event_id == event.id,
                EventMessage.status == "queued",
            )
            .all()
        }
        for recipient in recipients:
            if recipient.id in existing:
                continue
            body = render_message(template, event_context(event, recipient))
            if len(body) > 4_096:
                continue
            row = EventMessage(
                user_id=user.id,
                event_id=event.id,
                recipient_id=recipient.id,
                phone=recipient.phone,
                body=body,
                status="queued",
                scheduled_at=scheduled_at,
            )
            db.add(row)
            db.flush()
            message_ids.append(row.id)
            queued += 1
        db.commit()

        log_event(
            db,
            action="event.schedule",
            actor_user_id=user.id,
            resource_type="event",
            resource_id=str(event.id),
            ip_address=request.client.host if request.client else "",
            detail={
                "queued": queued,
                "skipped": len(recipients) - queued,
                "scheduled_at": str(scheduled_at),
            },
            commit=True,
        )

    return EventScheduleOut(
        event_id=event.id,
        queued=queued,
        skipped=max(0, len(recipients) - queued),
        scheduled_at=scheduled_at,
        preview=render_message(template, context),
        unresolved=unknown,
        message_ids=message_ids,
    )
