from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..models import (
    AdminFeatureFlag,
    SalesOpsBarcodeScan,
    SalesOpsDailyCounter,
    SalesOpsDispatch,
    SalesOpsYouTubeSignal,
)
from ..sales_ops_mail import auto_sync_due, list_instor_mails, sync_instor_mails
from ..security import get_current_user, require_admin
from ..services import GCSStorage, MailSender, YouTubeExtractor

router = APIRouter(prefix="/v1/sales-ops", tags=["sales-ops"])

DEFAULT_TOGGLES = {
    "whatsapp_auto_send_enabled": False,
    "whatsapp_daily_hard_cap": 49,
    "human_review_required": True,
    "erp_auto_followup_trigger": True,
    "barcode_mobile_scan_enabled": True,
    "youtube_free_tier_cron_enabled": True,
    "sales_pitch_kpi_overlay": True,
}
YOUTUBE_DAILY_QUOTA_LIMIT = 4000
DEFAULT_KEYWORDS = [
    "industrial stretch film manufacturing",
    "VCI anti corrosion bags",
    "stretch film extrusion plant",
    "barcode warehouse dispatch India",
    "industrial packaging machinery",
]


class TogglePatch(BaseModel):
    whatsapp_auto_send_enabled: bool | None = None
    whatsapp_daily_hard_cap: int | None = Field(default=None, ge=1, le=49)
    human_review_required: bool | None = None
    erp_auto_followup_trigger: bool | None = None
    barcode_mobile_scan_enabled: bool | None = None
    youtube_free_tier_cron_enabled: bool | None = None
    sales_pitch_kpi_overlay: bool | None = None


class MobileBarcodeScan(BaseModel):
    barcode: str = Field(min_length=3, max_length=128)
    sku: str = Field(default="STRETCH-FILM-23MIC", max_length=64)
    net_weight_kg: float = Field(gt=0, le=5000)
    customer_name: str = Field(min_length=2, max_length=255)
    customer_email: str | None = Field(default=None, max_length=255)
    customer_whatsapp: str | None = Field(default=None, max_length=64)
    trigger_followup: bool = True


class OutreachPrepareIn(BaseModel):
    contact_name: str = Field(min_length=2, max_length=255)
    company_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=8, max_length=32)
    catalog_url: str | None = Field(default=None, max_length=1024)
    youtube_video_link: str | None = Field(default=None, max_length=1024)


class DispatchIn(OutreachPrepareIn):
    email: str | None = Field(default=None, max_length=255)
    channels: list[Literal["email", "whatsapp", "youtube", "instagram"]] = Field(
        default_factory=lambda: ["email", "whatsapp"]
    )
    approve: bool = False


class YouTubeDiscoverIn(BaseModel):
    keywords: list[str] | None = Field(default=None, max_length=40)
    max_results: int = Field(default=8, ge=1, le=20)


class InstorMailSyncIn(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=50)


def _actor(user) -> str:
    return str(getattr(user, "email", "") or "")


def _flag(db: Session, name: str):
    row = db.query(AdminFeatureFlag).filter(AdminFeatureFlag.name == name).first()
    if row is None:
        return DEFAULT_TOGGLES[name]
    if name == "whatsapp_daily_hard_cap":
        return max(1, min(49, int(row.daily_limit or 0)))
    return bool(row.enabled)


def _toggles(db: Session) -> dict:
    return {name: _flag(db, name) for name in DEFAULT_TOGGLES}


def _set_flag(db: Session, name: str, value, actor: str) -> None:
    row = db.query(AdminFeatureFlag).filter(AdminFeatureFlag.name == name).first()
    if row is None:
        row = AdminFeatureFlag(name=name)
        db.add(row)
    if name == "whatsapp_daily_hard_cap":
        row.daily_limit = max(1, min(49, int(value)))
    else:
        row.enabled = bool(value)
    row.updated_by = actor


def _today() -> str:
    return str(date.today())


def _counter(db: Session) -> SalesOpsDailyCounter:
    day = _today()
    row = db.query(SalesOpsDailyCounter).filter(SalesOpsDailyCounter.day == day).first()
    if row is None:
        row = SalesOpsDailyCounter(day=day, whatsapp_sent=0, yt_quota_used=0)
        db.add(row)
        db.flush()
    return row


def _counter_payload(db: Session) -> dict:
    row = _counter(db)
    return {
        "date": row.day,
        "whatsapp_sent": int(row.whatsapp_sent or 0),
        "yt_quota_used": int(row.yt_quota_used or 0),
    }


def _base_url() -> str:
    return str(settings.TRACKING_BASE_URL or settings.OUTREACH_FORM_BASE_URL).rstrip("/")


def _safe_url(value: str | None, fallback_path: str) -> str:
    raw = str(value or "").strip() or fallback_path
    parsed = urlparse(raw)
    if not parsed.scheme and raw.startswith("/"):
        return f"{_base_url()}{raw}"
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="A valid http(s) URL is required")
    return raw


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 8 or len(digits) > 15:
        raise HTTPException(status_code=422, detail="A valid phone number is required")
    return digits


def _crm_storage() -> GCSStorage:
    return GCSStorage(bucket_name=settings.GCS_BUCKET_CRM or "sales-crm")


def _append_jsonl(storage: GCSStorage, blob_name: str, payload: dict) -> str:
    if not storage.available or storage._client is None:
        return ""
    try:
        bucket = storage._client.bucket(storage.bucket_name)
        blob = bucket.blob(blob_name)
        existing = (
            blob.download_as_bytes().decode("utf-8", errors="replace") if blob.exists() else ""
        )
        line = json.dumps(payload, ensure_ascii=False, default=str)
        blob.upload_from_string(f"{existing}{line}\n", content_type="application/x-ndjson")
        return f"gs://{storage.bucket_name}/{blob_name}"
    except Exception:  # noqa: BLE001 - new isolated path must never break existing routes
        return ""


def _render_whatsapp(
    contact_name: str,
    company_name: str,
    catalog_url: str,
    youtube_url: str,
) -> str:
    return (
        f"Hello {contact_name}\n\n"
        "Greetings from *Kalika Enterprises* (MIDC Ahmednagar - Est. 1990)!\n"
        f"Sharing our *Industrial Packaging Catalogue* for {company_name}:\n\n"
        "*Stretch Film (7-10 Tons/Day)*\n"
        "- Hand & Machine Rolls (23-51 Microns, Up to 300% Stretch)\n"
        "- VCI Bags, Custom BOPP Tape, Tarpaulin & Safety PPE\n\n"
        f"*Product Catalogue:* {catalog_url}\n"
        f"*Watch Plant Video:* {youtube_url}\n\n"
        "Reply *QUOTE* or call +91 96659 34999 for a factory quote."
    )


def _render_email(
    contact_name: str,
    company_name: str,
    catalog_url: str,
    youtube_url: str,
) -> tuple[str, str]:
    subject = "Industrial Stretch Film (7-10 Tons/Day) & Packaging Catalog — Kalika Enterprises"
    body = (
        f"Hello {contact_name},\n\n"
        "Greetings from Kalika Enterprises (MIDC Ahmednagar - Est. 1990).\n"
        f"Following up on your packaging requirements for {company_name}.\n\n"
        f"Product catalogue: {catalog_url}\n"
        f"Factory overview: {youtube_url}\n\n"
        "Stretch film 23-51 microns, up to 300% stretch, 7-10 tons/day in-house capacity, "
        "VCI bags, BOPP tape, tarpaulin and batch-traceable dispatch.\n\n"
        "Reply with sizes/quantities or WhatsApp +91 96659 34999 for a fast factory quote.\n\n"
        "Team Kalika Enterprises | Plot No M-59, MIDC Ahmednagar - 414 001 | www.kalikaindia.com"
    )
    return subject, body


def _render_social(company_name: str, catalog_url: str) -> dict:
    return {
        "youtube_title": "How High-Tensile Stretch Film is Made (7-10 Tons/Day) | Kalika Enterprises",
        "youtube_description": (
            "In-house LLDPE extrusion, closed-loop recycling and barcode-verified dispatch. "
            f"Catalogue: {catalog_url} | Bulk enquiries: +91 96659 34999"
        ),
        "instagram_caption": (
            "Zero transit damage starts with 300% high-stretch LLDPE film! Manufactured in-house "
            f"at Kalika Enterprises for {company_name}. Catalogue: {catalog_url} "
            "#KalikaEnterprises #StretchFilm #IndustrialPackaging #MakeInIndia"
        ),
    }


def _hook_pattern(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", title or "").strip()
    return re.split(r"\s[|—–]\s", cleaned, maxsplit=1)[0][:300]


def _live_youtube(keywords: list[str], max_results: int) -> list[dict]:
    api_key = settings.YOUTUBE_API_KEY
    if not api_key:
        return []
    signals: list[dict] = []
    with httpx.Client(timeout=10.0) as client:
        for keyword in keywords:
            response = client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": keyword,
                    "type": "video",
                    "maxResults": max_results,
                    "key": api_key,
                },
            )
            if response.status_code != 200:
                continue
            for item in response.json().get("items", []):
                video_id = str(item.get("id", {}).get("videoId", ""))
                if not video_id or any(signal["video_id"] == video_id for signal in signals):
                    continue
                snippet = item.get("snippet", {})
                signals.append(
                    {
                        "query": keyword,
                        "video_id": video_id,
                        "title": str(snippet.get("title", "")),
                        "video_url": f"https://www.youtube.com/watch?v={video_id}",
                        "channel": str(snippet.get("channelTitle", "")),
                        "view_count": 0,
                        "source_mode": "live_api",
                    }
                )
        if signals:
            response = client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "statistics",
                    "id": ",".join(signal["video_id"] for signal in signals[:50]),
                    "key": api_key,
                },
            )
            if response.status_code == 200:
                views = {
                    str(item.get("id", "")): int(
                        item.get("statistics", {}).get("viewCount", 0) or 0
                    )
                    for item in response.json().get("items", [])
                }
                for signal in signals:
                    signal["view_count"] = views.get(signal["video_id"], 0)
    return signals


@router.get("/admin/toggles")
def get_admin_toggles(db: Session = Depends(get_db), user=Depends(require_admin)):
    return {
        "toggles": _toggles(db),
        "daily_counters": _counter_payload(db),
        "actor": _actor(user),
    }


@router.patch("/admin/toggles")
def update_admin_toggles(
    patch: TogglePatch,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    changes = patch.model_dump(exclude_none=True)
    actor = _actor(user)
    for name, value in changes.items():
        _set_flag(db, name, value, actor)
    log_event(
        db,
        action="sales_ops_toggles_updated",
        actor_user_id=int(getattr(user, "id", 0) or 0),
        resource_type="admin_feature_flags",
        resource_id=",".join(sorted(changes)),
        detail={"keys": sorted(changes)},
    )
    db.commit()
    return {"status": "updated", "toggles": _toggles(db), "daily_counters": _counter_payload(db)}


@router.post("/erp/mobile-barcode-scan")
def record_mobile_barcode_scan(
    scan: MobileBarcodeScan,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    toggles = _toggles(db)
    if not toggles["barcode_mobile_scan_enabled"]:
        raise HTTPException(status_code=403, detail="Mobile barcode scan disabled by Admin toggle.")
    if scan.customer_email and "@" not in scan.customer_email:
        raise HTTPException(status_code=422, detail="A valid customer email is required")
    if scan.customer_whatsapp:
        _normalize_phone(scan.customer_whatsapp)

    followup = bool(scan.trigger_followup and toggles["erp_auto_followup_trigger"])
    event = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "barcode": scan.barcode,
        "sku": scan.sku,
        "net_weight_kg": scan.net_weight_kg,
        "customer_name": scan.customer_name,
        "customer_email": scan.customer_email or "",
        "customer_whatsapp": scan.customer_whatsapp or "",
        "followup_queued": followup,
        "weight_source": "MOBILE_CONFIRMED",
    }
    blob_name = f"{settings.GCS_PATH_SALES_APP_DATA.strip('/')}/mobile_scans/{_today()}.jsonl"
    gcs_uri = _append_jsonl(_crm_storage(), blob_name, event)
    row = SalesOpsBarcodeScan(
        user_id=int(getattr(user, "id", 0) or 0),
        barcode=scan.barcode,
        sku=scan.sku,
        net_weight_kg=scan.net_weight_kg,
        customer_name=scan.customer_name,
        customer_email=scan.customer_email or "",
        customer_whatsapp=scan.customer_whatsapp or "",
        trigger_followup=scan.trigger_followup,
        followup_status="READY_FOR_DISPATCH_NOTIFY" if followup else "LOGGED",
        gcs_uri=gcs_uri,
        created_by=_actor(user),
    )
    db.add(row)
    log_event(
        db,
        action="sales_ops_barcode_scan_recorded",
        actor_user_id=row.user_id,
        resource_type="sales_ops_barcode_scan",
        resource_id=scan.barcode,
        detail={"sku": scan.sku, "gcs_recorded": bool(gcs_uri)},
    )
    db.commit()
    db.refresh(row)
    return {
        "status": "recorded_to_gcs" if gcs_uri else "recorded_locally",
        "id": row.id,
        "event": event,
    }


@router.get("/erp/barcode-scans")
def list_barcode_scans(
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(SalesOpsBarcodeScan)
    if not bool(getattr(user, "role", "")) or getattr(user, "role", "") != "admin":
        query = query.filter(SalesOpsBarcodeScan.user_id == int(getattr(user, "id", 0) or 0))
    rows = (
        query.order_by(SalesOpsBarcodeScan.created_at.desc()).limit(max(1, min(limit, 200))).all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "barcode": row.barcode,
                "sku": row.sku,
                "net_weight_kg": row.net_weight_kg,
                "customer_name": row.customer_name,
                "followup_status": row.followup_status,
                "gcs_uri": row.gcs_uri,
                "created_at": str(row.created_at),
            }
            for row in rows
        ]
    }


@router.post("/outreach/prepare-or-send")
def prepare_or_send_outreach(
    payload: OutreachPrepareIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    toggles = _toggles(db)
    counter = _counter(db)
    phone = _normalize_phone(payload.phone)
    catalog_url = _safe_url(payload.catalog_url, "/api/public/catalog/catalog")
    youtube_url = _safe_url(
        payload.youtube_video_link,
        "https://www.youtube.com/results?search_query=Kalika+Enterprises+stretch+film",
    )
    message = _render_whatsapp(payload.contact_name, payload.company_name, catalog_url, youtube_url)
    wa_link = f"https://wa.me/{phone}?text={quote(message)}"
    cap = int(toggles["whatsapp_daily_hard_cap"])
    sent = int(counter.whatsapp_sent or 0)
    remaining = max(0, cap - sent)
    common = {
        "message_text": message,
        "one_click_whatsapp_url": wa_link,
        "remaining_daily_quota": remaining,
    }
    if not toggles["whatsapp_auto_send_enabled"] or toggles["human_review_required"]:
        return {"mode": "HUMAN_COPY_AND_REVIEW", **common}
    if sent >= cap:
        return {"mode": "DAILY_CAP_REACHED_FALLBACK_TO_HUMAN_COPY", **common}

    counter.whatsapp_sent = sent + 1
    row = SalesOpsDispatch(
        user_id=int(getattr(user, "id", 0) or 0),
        contact_name=payload.contact_name,
        company_name=payload.company_name,
        phone=phone,
        channels=["whatsapp"],
        preview=common,
        status="queued",
        approved_by=_actor(user),
        created_by=_actor(user),
    )
    db.add(row)
    log_event(
        db,
        action="sales_ops_whatsapp_queued",
        actor_user_id=row.user_id,
        resource_type="sales_ops_dispatch",
        resource_id=str(row.id or "pending"),
        detail={"remaining_daily_quota": cap - int(counter.whatsapp_sent)},
    )
    db.commit()
    return {
        "mode": "AUTO_QUEUED",
        **common,
        "sent_count_today": int(counter.whatsapp_sent),
        "remaining_daily_quota": cap - int(counter.whatsapp_sent),
    }


@router.post("/outreach/dispatch")
def dispatch_outreach(
    payload: DispatchIn,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    toggles = _toggles(db)
    counter = _counter(db)
    phone = _normalize_phone(payload.phone)
    catalog_url = _safe_url(payload.catalog_url, "/api/public/catalog/catalog")
    youtube_url = _safe_url(
        payload.youtube_video_link,
        "https://www.youtube.com/results?search_query=Kalika+Enterprises+stretch+film",
    )
    whatsapp_text = _render_whatsapp(
        payload.contact_name, payload.company_name, catalog_url, youtube_url
    )
    wa_link = f"https://wa.me/{phone}?text={quote(whatsapp_text)}"
    email_subject, email_body = _render_email(
        payload.contact_name, payload.company_name, catalog_url, youtube_url
    )
    preview = {
        "email": {"subject": email_subject, "body": email_body, "to": payload.email or ""},
        "whatsapp": {"message_text": whatsapp_text, "one_click_whatsapp_url": wa_link},
        "catalog_url": catalog_url,
        **_render_social(payload.company_name, catalog_url),
    }
    channels = list(dict.fromkeys(payload.channels)) or ["email"]
    row = SalesOpsDispatch(
        user_id=int(getattr(user, "id", 0) or 0),
        contact_name=payload.contact_name,
        company_name=payload.company_name,
        phone=phone,
        email=payload.email or "",
        channels=channels,
        preview=preview,
        status="pending_review",
        approved_by=_actor(user) if payload.approve else "",
        approved_at=datetime.now(timezone.utc) if payload.approve else None,
        created_by=_actor(user),
    )
    db.add(row)
    if toggles["human_review_required"] and not payload.approve:
        log_event(
            db,
            action="sales_ops_dispatch_pending_review",
            actor_user_id=row.user_id,
            resource_type="sales_ops_dispatch",
            resource_id=str(row.id or "pending"),
            detail={"channels": channels},
        )
        db.commit()
        db.refresh(row)
        return {"status": "pending_review", "dispatch_id": row.id, "preview": preview}

    email_result = {"status": "not_requested"}
    if "email" in channels:
        if payload.email and "@" in payload.email and settings.SMTP_HOST:
            sender = MailSender(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                settings.SMTP_USER or settings.GMAIL_ADDRESS_KALISOFTAI,
                settings.GMAIL_APP_PASSWORD_KALISOFTAI or settings.GMAIL_APP_PASSWORD,
            )
            try:
                result = sender.send(
                    to=payload.email,
                    subject=email_subject,
                    body=email_body,
                    from_email=settings.GMAIL_ADDRESS_KALISOFTAI or settings.SMTP_USER or None,
                )
                email_result = {"status": "sent", "message_id": result.get("message_id", "")}
            except Exception as exc:  # noqa: BLE001 - caller needs an honest channel status
                email_result = {"status": "failed", "error": str(exc)[:300]}
        else:
            email_result = {"status": "skipped", "reason": "email_or_smtp_not_configured"}

    whatsapp_result = {"status": "not_requested"}
    if "whatsapp" in channels:
        cap = int(toggles["whatsapp_daily_hard_cap"])
        sent = int(counter.whatsapp_sent or 0)
        if not toggles["whatsapp_auto_send_enabled"]:
            whatsapp_result = {
                "status": "human_copy",
                "message_text": whatsapp_text,
                "one_click_whatsapp_url": wa_link,
                "remaining_daily_quota": max(0, cap - sent),
            }
        elif sent >= cap:
            whatsapp_result = {
                "status": "daily_cap_reached",
                "message_text": whatsapp_text,
                "one_click_whatsapp_url": wa_link,
                "remaining_daily_quota": 0,
            }
        else:
            counter.whatsapp_sent = sent + 1
            whatsapp_result = {
                "status": "queued",
                "remaining_daily_quota": max(0, cap - int(counter.whatsapp_sent)),
            }

    social_result = {
        "youtube": "queued_preview_only" if "youtube" in channels else "not_requested",
        "instagram": "queued_preview_only" if "instagram" in channels else "not_requested",
    }
    row.status = "dispatched"
    log_event(
        db,
        action="sales_ops_dispatch_approved",
        actor_user_id=row.user_id,
        resource_type="sales_ops_dispatch",
        resource_id=str(row.id or "pending"),
        detail={"channels": channels, "email_status": email_result["status"]},
    )
    db.commit()
    db.refresh(row)
    return {
        "status": "dispatched",
        "dispatch_id": row.id,
        "channels": {"email": email_result, "whatsapp": whatsapp_result, **social_result},
        "preview": preview,
        "daily_counters": _counter_payload(db),
    }


@router.post("/youtube/discover")
def discover_youtube(
    payload: YouTubeDiscoverIn,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    toggles = _toggles(db)
    if not toggles["youtube_free_tier_cron_enabled"]:
        raise HTTPException(status_code=403, detail="YouTube discovery disabled by Admin toggle.")
    counter = _counter(db)
    unit_cost = 101 if settings.YOUTUBE_API_KEY else 100
    remaining_quota = max(0, YOUTUBE_DAILY_QUOTA_LIMIT - int(counter.yt_quota_used or 0))
    search_count = min(
        len(payload.keywords or DEFAULT_KEYWORDS),
        40,
        remaining_quota // unit_cost,
    )
    if search_count <= 0:
        raise HTTPException(status_code=429, detail="YouTube daily quota guard reached")
    keywords = list(payload.keywords or DEFAULT_KEYWORDS)[:search_count]
    signals = _live_youtube(keywords, payload.max_results)
    source_mode = "live_api" if signals else "deterministic_stub"
    if not signals:
        raw = YouTubeExtractor().search_signals(keywords, max_results=payload.max_results)
        signals = [
            {
                "query": item.get("query", ""),
                "video_id": "",
                "title": str(item.get("title", "")).replace("[signal] ", ""),
                "video_url": item.get("video_url", ""),
                "channel": "",
                "view_count": 0,
                "source_mode": source_mode,
            }
            for item in raw
        ]
    counter.yt_quota_used = int(counter.yt_quota_used or 0) + search_count * unit_cost
    for item in signals:
        db.add(
            SalesOpsYouTubeSignal(
                query=item["query"],
                video_id=item.get("video_id", ""),
                title=item.get("title", ""),
                video_url=item.get("video_url", ""),
                channel=item.get("channel", ""),
                view_count=int(item.get("view_count", 0) or 0),
                hook_pattern=_hook_pattern(item.get("title", "")),
                source_mode=source_mode,
            )
        )
    log_event(
        db,
        action="sales_ops_youtube_discovery",
        actor_user_id=int(getattr(user, "id", 0) or 0),
        resource_type="sales_ops_youtube_signal",
        resource_id=f"{source_mode}:{search_count}",
        detail={"searches": search_count, "quota_units": search_count * unit_cost},
    )
    db.commit()
    return {
        "status": "discovered",
        "source_mode": source_mode,
        "signals": signals,
        "quota_used_today": int(counter.yt_quota_used),
        "quota_limit": YOUTUBE_DAILY_QUOTA_LIMIT,
    }


@router.get("/youtube/trends")
def list_youtube_trends(
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    rows = (
        db.query(SalesOpsYouTubeSignal)
        .order_by(SalesOpsYouTubeSignal.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "query": row.query,
                "title": row.title,
                "video_url": row.video_url,
                "view_count": row.view_count,
                "hook_pattern": row.hook_pattern,
                "source_mode": row.source_mode,
                "created_at": str(row.created_at),
            }
            for row in rows
        ]
    }


# ---------------------------------------------------------------------------
# Instor India incoming mail desk (read-only mailbox capture + AI summaries)
# ---------------------------------------------------------------------------


@router.post("/mail/instor/sync")
def sync_instor_mail(
    payload: InstorMailSyncIn | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Explicitly pull new mail from the configured Kalika Gmail account."""
    result = sync_instor_mails(
        db,
        user_id=int(getattr(user, "id", 0) or 0),
        actor=_actor(user),
        limit=(payload.limit if payload else None),
    )
    # Return the status inline instead of raising: a transient IMAP failure must
    # not turn the whole Sales Ops view into a hard HTTP error.
    return result


@router.get("/mail/instor")
def list_instor_mail(
    limit: int = 200,
    date: str | None = None,
    auto_sync: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List Instor mail grouped by date/time; refresh new mail when due."""
    sync_result: dict | None = None
    if auto_sync and auto_sync_due(db):
        sync_result = sync_instor_mails(
            db,
            user_id=int(getattr(user, "id", 0) or 0),
            actor=_actor(user),
            limit=settings.SALES_OPS_INSTOR_SYNC_LIMIT,
        )
    payload = list_instor_mails(db, limit=limit, date_filter=date or "")
    payload["sync"] = sync_result or {
        "status": "skipped",
        "reason": "synced_recently" if auto_sync else "auto_sync_disabled",
    }
    return payload
