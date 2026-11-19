from __future__ import annotations

import io
import re
import secrets
import zipfile
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..importer import records_from_bytes
from ..interaction_dump import parse_whatsapp_chat
from ..models import (
    MarketingCompany,
    OutreachEngagementEvent,
    OutreachSmartTemplate,
    OutreachWhatsAppCampaign,
    OutreachWhatsAppMessage,
    Product,
    ProductRate,
    User,
)
from ..pipeline_templates import CATALOGUE_LINK, PROFILE_LINK
from ..security import get_current_user, is_admin_user, require_admin
from ..wechaty import WechatyGateway, verify_webhook_signature

router = APIRouter(prefix="/outreach-whatsapp", tags=["outreach-whatsapp"])

CONTACT_PHONE = "+91 94055 36016"
WEBSITE_URL = "https://www.kalikaindia.com"
CTA = (
    f"Reply YES for a quote or call/WhatsApp {CONTACT_PHONE}. "
    f"Explore {WEBSITE_URL} - Team Kalika"
)
SAMPLE_RATES = (
    ("stretch-film", "Stretch Film", 160.0),
    ("baby-roll", "Baby Roll", 164.0),
)
DEFAULT_TEMPLATES = (
    {
        "name": "Daily rate + catalogue",
        "category": "rates",
        "body": (
            "Namaste {{name}} ji, {{agent}} from Kalika Enterprises. "
            "For {{company}}, today's rate for {{product}} is {{rate}} (GST extra). "
            "Catalogue: {{catalog_url}} | Profile: {{profile_url}}\n"
            "{{requirements}}"
        ),
    },
    {
        "name": "Requirement follow-up",
        "category": "follow_up",
        "body": (
            "Namaste {{name}} ji, following up on the requirement shared by {{company}}: "
            "{{requirements}}. Current rate: {{rate}}. Product details: {{product_url}} | "
            "Catalogue: {{catalog_url}}"
        ),
    },
    {
        "name": "New introduction",
        "category": "introduction",
        "body": (
            "Namaste {{name}} ji, {{agent}} from Kalika Enterprises, Ahmednagar. "
            "We manufacture stretch film, polybags, VCI bags, tapes and packaging materials. "
            "Website: {{website_url}} | Catalogue: {{catalog_url}} | Rate: {{rate}}"
        ),
    },
)
PRODUCT_KEYWORDS = (
    "stretch film",
    "baby roll",
    "polybag",
    "poly bag",
    "vci",
    "bopp",
    "masking tape",
    "tarpaulin",
    "shade net",
    "shrink film",
    "hand gloves",
    "strap",
)


class SmartTemplateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    category: str = Field(default="general", max_length=64)
    body: str = Field(..., min_length=10, max_length=8000)
    variables: list[str] = Field(default_factory=list)


class SmartTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    body: str | None = Field(default=None, max_length=8000)
    variables: list[str] | None = None


class PreviewIn(BaseModel):
    template_id: int
    rate_ids: list[int] = Field(default_factory=list)
    contact_ids: list[int] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50)


class RateIn(BaseModel):
    product_id: int = Field(..., ge=1)
    rate: float = Field(..., gt=0, le=1_000_000)
    effective_date: str = Field(default="", max_length=10)
    notes: str = Field(default="", max_length=2000)


class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]
    notes: str = Field(default="", max_length=2000)


class CampaignIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    template_id: int = Field(..., ge=1)
    rate_ids: list[int] = Field(default_factory=list)
    contact_ids: list[int] = Field(default_factory=list)
    segment: str = Field(default="", max_length=64)
    limit: int = Field(default=100, ge=1, le=500)


class EngagementIn(BaseModel):
    message_id: int | None = None
    provider_id: str = ""
    status: str = Field(..., min_length=2, max_length=32)
    event_id: str = ""
    duration_ms: int = Field(default=0, ge=0)
    target_url: str = Field(default="", max_length=1024)
    meta: dict[str, Any] = Field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _today() -> str:
    return _now().strftime("%Y-%m-%d")


def _phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0"):
        return ""
    if len(digits) == 10:
        digits = "91" + digits
    return digits if 11 <= len(digits) <= 15 else ""


def _company_key(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip().lower())


def _template_out(row: OutreachSmartTemplate) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "category": row.category,
        "body": row.body,
        "variables": row.variables or [],
        "status": row.status,
        "version": row.version,
        "created_by": row.created_by,
        "approved_by": row.approved_by,
        "approved_at": str(row.approved_at) if row.approved_at else None,
        "updated_at": str(row.updated_at),
    }


def _rate_out(rate: ProductRate, product: Product | None = None) -> dict:
    return {
        "id": rate.id,
        "product_id": rate.product_id,
        "product_name": product.name if product else "",
        "rate": rate.rate,
        "currency": rate.currency,
        "unit": rate.unit,
        "effective_date": rate.effective_date,
        "status": rate.status,
        "notes": rate.notes,
        "approved_by": rate.approved_by,
        "reviewed_at": str(rate.reviewed_at) if rate.reviewed_at else None,
    }


def _contact_out(row: MarketingCompany) -> dict:
    return {
        "id": row.id,
        "company": row.company,
        "name": row.contact_name,
        "phone": row.phone,
        "requirements": row.requirements,
        "category": row.category,
        "segment": row.segment or "imported",
        "marketing_approved": bool(row.marketing_approved),
        "source_reference": row.source_reference,
    }


def _campaign_out(row: OutreachWhatsAppCampaign) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "template_id": row.template_id,
        "segment": row.segment,
        "rate_ids": row.rate_ids or [],
        "status": row.status,
        "total": row.total,
        "sent_count": row.sent_count,
        "delivered_count": row.delivered_count,
        "read_count": row.read_count,
        "failed_count": row.failed_count,
        "approved_by": row.approved_by,
        "approved_at": str(row.approved_at) if row.approved_at else None,
        "sent_at": str(row.sent_at) if row.sent_at else None,
        "created_at": str(row.created_at),
    }


def _message_out(row: OutreachWhatsAppMessage) -> dict:
    return {
        "id": row.id,
        "campaign_id": row.campaign_id,
        "contact_id": row.contact_id,
        "phone": row.phone,
        "name": row.name,
        "company": row.company,
        "rendered_body": row.rendered_body,
        "status": row.status,
        "provider_id": row.provider_id,
        "sent_at": str(row.sent_at) if row.sent_at else None,
        "delivered_at": str(row.delivered_at) if row.delivered_at else None,
        "read_at": str(row.read_at) if row.read_at else None,
        "failed_at": str(row.failed_at) if row.failed_at else None,
        "error": row.error,
        "links": row.links or {},
    }


def _rate_text(
    db: Session, rate_ids: list[int], user_id: int
) -> tuple[str, list[ProductRate]]:
    rates = [db.get(ProductRate, rate_id) for rate_id in rate_ids]
    rates = [
        rate
        for rate in rates
        if rate is not None and rate.status == "approved" and rate.user_id == user_id
    ]
    products = {p.id: p for p in db.query(Product).filter(Product.user_id == user_id).all()}
    text = " | ".join(
        f"{products[r.product_id].name if r.product_id in products else 'Product'} "
        f"₹{r.rate:g}/{r.unit}"
        for r in rates
    )
    return text or "Please contact us for today's rate", rates


def _render(body: str, context: dict[str, str]) -> str:
    rendered = body
    for key, value in context.items():
        rendered = rendered.replace("{{" + key + "}}", value).replace("{" + key + "}", value)
    rendered = rendered.rstrip()
    if not rendered.endswith(CTA):
        rendered = f"{rendered}\n\n{CTA}"
    return rendered


def _tracking_base(request: Request) -> str:
    configured = (settings.TRACKING_BASE_URL or "").strip().rstrip("/")
    return configured or str(request.base_url).rstrip("/")


def _tracked_url(request: Request, token: str, target: str, event: str) -> str:
    base = _tracking_base(request)
    return (
        f"{base}/api/outreach-whatsapp/public/track/{token}"
        f"?event={event}&target={quote(target, safe='')}"
    )


def _contact_context(db: Session, contact: MarketingCompany | None) -> dict[str, str]:
    if contact is None:
        return {"name": "Sir/Madam", "company": "your company", "requirements": ""}
    requirements = " ".join(
        part.strip() for part in (contact.requirements or "").splitlines() if part.strip()
    )
    return {
        "name": contact.contact_name or "Sir/Madam",
        "company": contact.company or "your company",
        "requirements": f"Noted requirement: {requirements}" if requirements else "",
    }


def _render_context(
    request: Request,
    db: Session,
    body: str,
    contact: MarketingCompany | None,
    rate_text_value: str,
    token: str = "",
) -> tuple[str, dict[str, str]]:
    ctx = _contact_context(db, contact)
    catalog = _tracked_url(request, token, CATALOGUE_LINK, "catalog_download") if token else CATALOGUE_LINK
    profile = _tracked_url(request, token, PROFILE_LINK, "profile_download") if token else PROFILE_LINK
    product = _tracked_url(request, token, WEBSITE_URL, "product_link") if token else WEBSITE_URL
    ctx.update(
        {
            "agent": settings.PROJECT_NAME or "Team Kalika",
            "rate": rate_text_value,
            "product": "packaging material",
            "catalog_url": catalog,
            "profile_url": profile,
            "product_url": product,
            "website_url": WEBSITE_URL,
            "contact_phone": CONTACT_PHONE,
            "whatsapp": CONTACT_PHONE,
            "cta": CTA,
        }
    )
    return _render(body, ctx), ctx


def _segment_for(contact: MarketingCompany) -> str:
    text = f"{contact.requirements or ''} {contact.call_status or ''} {contact.notes or ''}".lower()
    if "urgent" in text or "quote" in text or "rate" in text:
        return "hot"
    if "not answered" in text or "busy" in text or "call later" in text:
        return "follow_up"
    return "leads"


def _refresh_campaign(db: Session, campaign_id: int) -> None:
    campaign = db.get(OutreachWhatsAppCampaign, campaign_id)
    if campaign is None:
        return
    messages = (
        db.query(OutreachWhatsAppMessage)
        .filter(OutreachWhatsAppMessage.campaign_id == campaign_id)
        .all()
    )
    campaign.total = len(messages)
    campaign.sent_count = sum(1 for m in messages if m.sent_at is not None)
    campaign.delivered_count = sum(1 for m in messages if m.delivered_at is not None)
    campaign.read_count = sum(1 for m in messages if m.read_at is not None)
    campaign.failed_count = sum(1 for m in messages if m.failed_at is not None)
    campaign.updated_at = _now()


def _apply_event(
    db: Session,
    *,
    message: OutreachWhatsAppMessage,
    event_type: str,
    provider_event_id: str,
    target_url: str,
    duration_ms: int,
    meta: dict[str, Any],
) -> bool:
    event = event_type.lower()
    if provider_event_id:
        exists = (
            db.query(OutreachEngagementEvent)
            .filter(OutreachEngagementEvent.provider_event_id == provider_event_id)
            .first()
        )
        if exists is not None:
            return False
    db.add(
        OutreachEngagementEvent(
            user_id=message.user_id,
            message_id=message.id,
            event_type=event,
            provider_event_id=provider_event_id or None,
            target_url=target_url,
            duration_ms=max(0, duration_ms),
            meta=meta,
        )
    )
    now = _now()
    if event == "delivered":
        message.delivered_at = message.delivered_at or now
        message.status = "delivered" if message.status != "read" else message.status
    elif event == "read":
        message.read_at = message.read_at or now
        message.delivered_at = message.delivered_at or now
        message.status = "read"
    elif event == "failed":
        message.failed_at = message.failed_at or now
        message.status = "failed"
    _refresh_campaign(db, message.campaign_id)
    return True


def _pdf_text(data: bytes) -> str:
    chunks = re.findall(rb"\((?:\\.|[^()\\])*\)", data or b"", flags=re.S)
    text: list[str] = []
    for chunk in chunks:
        raw = chunk[1:-1].replace(rb"\(", b"(").replace(rb"\)", b")")
        value = raw.decode("latin-1", errors="replace").strip()
        if len(value) >= 3:
            text.append(value)
    return " ".join(text)


def _requirements_from_text(text: str) -> str:
    parts = [part.strip() for part in re.split(r"[\n.!?]", text or "") if part.strip()]
    matched = [
        part
        for part in parts
        if any(keyword in part.lower() for keyword in (*PRODUCT_KEYWORDS, "rate", "price", "quote", "requirement"))
    ]
    return " | ".join(matched[:8])[:2000]


@router.get("/status")
def status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gateway = WechatyGateway()
    return {
        "enabled": settings.WHATSAPP_ENABLED,
        "gateway": gateway.health(),
        "templates": db.query(OutreachSmartTemplate).filter(OutreachSmartTemplate.user_id == user.id).count(),
        "campaigns": db.query(OutreachWhatsAppCampaign).filter(OutreachWhatsAppCampaign.user_id == user.id).count(),
        "messages": db.query(OutreachWhatsAppMessage).filter(OutreachWhatsAppMessage.user_id == user.id).count(),
    }


@router.post("/bootstrap")
def bootstrap(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    today = _today()
    products = {p.code: p for p in db.query(Product).filter(Product.user_id == user.id).all()}
    created_products = 0
    for code, name, _ in SAMPLE_RATES:
        if code in products:
            continue
        product = Product(
            user_id=user.id,
            code=code,
            name=name,
            category="packaging",
            unit="kg",
            description=f"{name} daily rate",
        )
        db.add(product)
        db.flush()
        products[code] = product
        created_products += 1

    created_rates = 0
    for code, _, amount in SAMPLE_RATES:
        product = products[code]
        exists = (
            db.query(ProductRate)
            .filter(
                ProductRate.user_id == user.id,
                ProductRate.product_id == product.id,
                ProductRate.effective_date == today,
                ProductRate.status.in_(["pending", "approved"]),
            )
            .first()
        )
        if exists is not None:
            continue
        db.add(
            ProductRate(
                user_id=user.id,
                product_id=product.id,
                rate=amount,
                currency="INR",
                unit="kg",
                effective_date=today,
                status="pending",
                submitted_by=user.email,
                notes="Sample daily rate - awaiting approval",
            )
        )
        created_rates += 1

    created_templates = 0
    for item in DEFAULT_TEMPLATES:
        exists = (
            db.query(OutreachSmartTemplate)
            .filter(OutreachSmartTemplate.user_id == user.id, OutreachSmartTemplate.name == item["name"])
            .first()
        )
        if exists is not None:
            continue
        db.add(
            OutreachSmartTemplate(
                user_id=user.id,
                name=item["name"],
                category=item["category"],
                body=item["body"],
                variables=["name", "company", "requirements", "rate", "catalog_url", "cta"],
                status="draft",
                created_by=user.email,
            )
        )
        created_templates += 1
    db.commit()
    return {
        "products_created": created_products,
        "rates_created": created_rates,
        "templates_created": created_templates,
        "rates": [{"product": name, "rate": amount, "unit": "kg"} for _, name, amount in SAMPLE_RATES],
    }


@router.get("/templates")
def list_templates(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(OutreachSmartTemplate)
        .filter(OutreachSmartTemplate.user_id == user.id)
        .order_by(OutreachSmartTemplate.id.desc())
        .all()
    )
    return [_template_out(row) for row in rows]


@router.post("/templates", status_code=201)
def create_template(
    payload: SmartTemplateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exists = (
        db.query(OutreachSmartTemplate)
        .filter(OutreachSmartTemplate.user_id == user.id, OutreachSmartTemplate.name == payload.name)
        .first()
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="Template name already exists")
    row = OutreachSmartTemplate(
        user_id=user.id,
        created_by=user.name or user.email,
        status="draft",
        **payload.model_dump(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _template_out(row)


@router.patch("/templates/{template_id}")
def update_template(
    template_id: int,
    payload: SmartTemplateUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(OutreachSmartTemplate, template_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Template not found")
    changes = payload.model_dump(exclude_unset=True)
    if "body" in changes and changes["body"] and changes["body"] != row.body:
        row.version += 1
        row.status = "draft"
        row.approved_by = ""
        row.approved_at = None
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return _template_out(row)


@router.post("/templates/{template_id}/approve")
def approve_template(
    template_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.get(OutreachSmartTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    row.status = "approved"
    row.approved_by = user.name or user.email
    row.approved_at = _now()
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    log_event(
        db,
        action="outreach.whatsapp.template_approve",
        actor_user_id=user.id,
        resource_type="outreach_smart_template",
        resource_id=str(row.id),
        detail={"name": row.name, "version": row.version},
        commit=True,
    )
    return _template_out(row)


@router.post("/templates/preview")
def preview_template(
    payload: PreviewIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = db.get(OutreachSmartTemplate, payload.template_id)
    if template is None or template.user_id != user.id:
        raise HTTPException(status_code=404, detail="Template not found")
    rate_text_value, _ = _rate_text(db, payload.rate_ids, user.id)
    contacts: list[MarketingCompany] = []
    if payload.contact_ids:
        contacts = (
            db.query(MarketingCompany)
            .filter(MarketingCompany.user_id == user.id, MarketingCompany.id.in_(payload.contact_ids))
            .limit(payload.limit)
            .all()
        )
    previews = []
    for contact in contacts or [None]:
        body, _ = _render_context(
            request, db, template.body, contact, rate_text_value, token="preview"
        )
        previews.append(
            {
                "contact_id": contact.id if contact else 0,
                "name": contact.contact_name if contact else "Sample Contact",
                "company": contact.company if contact else "Sample Company",
                "body": body,
            }
        )
    return {"template_id": template.id, "status": template.status, "previews": previews}


@router.get("/rates")
def list_rates(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rates = (
        db.query(ProductRate)
        .filter(ProductRate.user_id == user.id)
        .order_by(ProductRate.effective_date.desc(), ProductRate.id.desc())
        .limit(200)
        .all()
    )
    products = {p.id: p for p in db.query(Product).filter(Product.user_id == user.id).all()}
    return {
        "date": _today(),
        "items": [_rate_out(rate, products.get(rate.product_id)) for rate in rates],
        "pending_count": sum(1 for rate in rates if rate.status == "pending"),
        "approved_count": sum(1 for rate in rates if rate.status == "approved"),
    }


@router.post("/rates", status_code=201)
def submit_rate(
    payload: RateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.get(Product, payload.product_id)
    if product is None or product.user_id != user.id:
        raise HTTPException(status_code=404, detail="Product not found")
    rate = ProductRate(
        user_id=user.id,
        product_id=product.id,
        rate=payload.rate,
        currency="INR",
        unit=product.unit or "kg",
        effective_date=payload.effective_date or _today(),
        status="pending",
        submitted_by=user.name or user.email,
        notes=payload.notes,
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return _rate_out(rate, product)


@router.post("/rates/{rate_id}/review")
def review_rate(
    rate_id: int,
    payload: ReviewIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rate = db.get(ProductRate, rate_id)
    if rate is None:
        raise HTTPException(status_code=404, detail="Rate not found")
    if rate.status != "pending":
        raise HTTPException(status_code=409, detail=f"Rate already {rate.status}")
    if payload.decision == "approved":
        (
            db.query(ProductRate)
            .filter(
                ProductRate.product_id == rate.product_id,
                ProductRate.status == "approved",
                ProductRate.id != rate.id,
            )
            .update({"status": "superseded"}, synchronize_session=False)
        )
    rate.status = payload.decision
    rate.approved_by = user.name or user.email
    rate.reviewed_at = _now()
    if payload.notes:
        rate.notes = payload.notes
    db.commit()
    db.refresh(rate)
    log_event(
        db,
        action="outreach.whatsapp.rate_review",
        actor_user_id=user.id,
        resource_type="product_rate",
        resource_id=str(rate.id),
        detail={"decision": payload.decision, "product_id": rate.product_id},
        commit=True,
    )
    return _rate_out(rate, db.get(Product, rate.product_id))


@router.get("/contacts")
def list_contacts(
    q: str = "",
    segment: str = "",
    approved_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(MarketingCompany).filter(MarketingCompany.user_id == user.id)
    if approved_only:
        query = query.filter(MarketingCompany.marketing_approved.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(
            MarketingCompany.company.ilike(like)
            | MarketingCompany.contact_name.ilike(like)
            | MarketingCompany.phone.ilike(like)
            | MarketingCompany.requirements.ilike(like)
        )
    if segment:
        query = query.filter(MarketingCompany.segment == segment)
    rows = query.order_by(MarketingCompany.id.desc()).limit(limit).all()
    return [_contact_out(row) for row in rows]


@router.post("/contacts/{contact_id}/approve")
def approve_contact(
    contact_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.get(MarketingCompany, contact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    row.marketing_approved = True
    db.commit()
    db.refresh(row)
    log_event(
        db,
        action="outreach.whatsapp.contact_approve",
        actor_user_id=user.id,
        resource_type="marketing_company",
        resource_id=str(row.id),
        detail={"company": row.company},
        commit=True,
    )
    return _contact_out(row)


@router.get("/segments")
def list_segments(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(MarketingCompany).filter(MarketingCompany.user_id == user.id).all()
    counts: dict[str, int] = defaultdict(int)
    updated = 0
    for row in rows:
        segment = _segment_for(row)
        counts[segment] += 1
        if row.segment != segment and row.marketing_approved:
            row.segment = segment
            updated += 1
    if updated:
        db.commit()
    return [
        {"key": key, "label": key.replace("_", " ").title(), "count": counts.get(key, 0)}
        for key in ("hot", "follow_up", "leads")
    ]


@router.post("/campaigns", status_code=201)
def create_campaign(
    payload: CampaignIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = db.get(OutreachSmartTemplate, payload.template_id)
    if template is None or template.user_id != user.id:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.status != "approved":
        raise HTTPException(status_code=409, detail="Template must be approved before sending")

    rate_text_value, rates = _rate_text(db, payload.rate_ids, user.id)
    if payload.rate_ids and not rates:
        raise HTTPException(status_code=409, detail="No approved rates selected")

    contact_query = db.query(MarketingCompany).filter(MarketingCompany.user_id == user.id)
    if payload.contact_ids:
        contact_query = contact_query.filter(MarketingCompany.id.in_(payload.contact_ids))
    if payload.segment:
        contact_query = contact_query.filter(MarketingCompany.segment == payload.segment)
    contacts = contact_query.limit(payload.limit).all()
    if not contacts:
        raise HTTPException(status_code=400, detail="No approved contacts selected")
    not_approved = [c.id for c in contacts if not c.marketing_approved]
    if not_approved:
        raise HTTPException(status_code=409, detail="Imported contacts need approval before marketing")

    campaign = OutreachWhatsAppCampaign(
        user_id=user.id,
        name=payload.name,
        template_id=template.id,
        segment=payload.segment,
        rate_ids=payload.rate_ids,
        status="pending_review",
        total=len(contacts),
        created_by=user.name or user.email,
    )
    db.add(campaign)
    db.flush()

    for contact in contacts:
        token = secrets.token_urlsafe(18)
        body, ctx = _render_context(
            request, db, template.body, contact, rate_text_value, token=token
        )
        message = OutreachWhatsAppMessage(
            user_id=user.id,
            campaign_id=campaign.id,
            contact_id=contact.id,
            contact_type="marketing_companies",
            phone=_phone(contact.phone or ""),
            name=contact.contact_name or "",
            company=contact.company or "",
            rendered_body=body,
            links={
                "catalog_url": ctx["catalog_url"],
                "product_url": ctx["product_url"],
                "website_url": WEBSITE_URL,
                "token": token,
            },
            status="pending_review",
            track_token=token,
        )
        db.add(message)
    db.commit()
    db.refresh(campaign)
    log_event(
        db,
        action="outreach.whatsapp.campaign_create",
        actor_user_id=user.id,
        resource_type="outreach_campaign",
        resource_id=str(campaign.id),
        detail={"name": campaign.name, "recipients": campaign.total},
        commit=True,
    )
    return _campaign_out(campaign)


@router.get("/campaigns")
def list_campaigns(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(OutreachWhatsAppCampaign)
        .filter(OutreachWhatsAppCampaign.user_id == user.id)
        .order_by(OutreachWhatsAppCampaign.id.desc())
        .limit(100)
        .all()
    )
    return [_campaign_out(row) for row in rows]


@router.get("/campaigns/{campaign_id}")
def get_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = db.get(OutreachWhatsAppCampaign, campaign_id)
    if campaign is None or campaign.user_id != user.id:
        raise HTTPException(status_code=404, detail="Campaign not found")
    messages = (
        db.query(OutreachWhatsAppMessage)
        .filter(OutreachWhatsAppMessage.campaign_id == campaign.id)
        .order_by(OutreachWhatsAppMessage.id)
        .all()
    )
    return {**_campaign_out(campaign), "messages": [_message_out(row) for row in messages]}


@router.post("/campaigns/{campaign_id}/approve")
def approve_campaign(
    campaign_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    campaign = db.get(OutreachWhatsAppCampaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    messages = (
        db.query(OutreachWhatsAppMessage)
        .filter(
            OutreachWhatsAppMessage.campaign_id == campaign.id,
            OutreachWhatsAppMessage.status == "pending_review",
        )
        .all()
    )
    for message in messages:
        message.status = "approved"
    campaign.status = "approved"
    campaign.approved_by = user.name or user.email
    campaign.approved_at = _now()
    campaign.updated_at = _now()
    db.commit()
    log_event(
        db,
        action="outreach.whatsapp.campaign_approve",
        actor_user_id=user.id,
        resource_type="outreach_campaign",
        resource_id=str(campaign.id),
        detail={"approved_messages": len(messages)},
        commit=True,
    )
    return {**_campaign_out(campaign), "approved_messages": len(messages)}


@router.post("/campaigns/{campaign_id}/send")
def send_campaign(
    campaign_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.WHATSAPP_ENABLED:
        raise HTTPException(status_code=503, detail="WhatsApp channel is disabled")
    campaign = db.get(OutreachWhatsAppCampaign, campaign_id)
    if campaign is None or campaign.user_id != user.id:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != "approved":
        raise HTTPException(status_code=409, detail="Campaign must be approved before sending")
    messages = (
        db.query(OutreachWhatsAppMessage)
        .filter(
            OutreachWhatsAppMessage.campaign_id == campaign.id,
            OutreachWhatsAppMessage.status == "approved",
        )
        .all()
    )
    gateway = WechatyGateway()
    sent = failed = 0
    for message in messages:
        if not message.phone:
            message.status = "failed"
            message.error = "Invalid WhatsApp number"
            message.failed_at = _now()
            failed += 1
            continue
        try:
            result = gateway.send_text(message.phone, message.rendered_body)
            message.provider_id = str(result.get("id", ""))
            message.status = "sent"
            message.sent_at = _now()
            message.error = ""
            sent += 1
        except Exception as exc:  # noqa: BLE001 - gateway failure is per-message
            message.status = "failed"
            message.error = f"{type(exc).__name__}: {exc}"[:512]
            message.failed_at = _now()
            failed += 1
    campaign.status = "sent"
    campaign.sent_at = _now()
    _refresh_campaign(db, campaign.id)
    db.commit()
    log_event(
        db,
        action="outreach.whatsapp.campaign_send",
        actor_user_id=user.id,
        resource_type="outreach_campaign",
        resource_id=str(campaign.id),
        ip_address=request.client.host if request.client else "",
        detail={"sent": sent, "failed": failed},
        commit=True,
    )
    return {**_campaign_out(campaign), "sent": sent, "failed": failed}


@router.post("/webhook")
async def engagement_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    if not verify_webhook_signature(raw, request.headers.get("x-wechaty-signature", "")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = EngagementIn.model_validate_json(raw or b"{}")
    except Exception as exc:  # noqa: BLE001 - invalid webhook payload
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {exc}") from exc
    message = None
    if payload.message_id:
        message = db.get(OutreachWhatsAppMessage, payload.message_id)
    if message is None and payload.provider_id:
        message = (
            db.query(OutreachWhatsAppMessage)
            .filter(OutreachWhatsAppMessage.provider_id == payload.provider_id)
            .first()
        )
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    created = _apply_event(
        db,
        message=message,
        event_type=payload.status,
        provider_event_id=payload.event_id,
        target_url=payload.target_url,
        duration_ms=payload.duration_ms,
        meta=payload.meta,
    )
    db.commit()
    return {"ok": True, "created": created, "message_id": message.id}


@router.get("/public/track/{token}")
def track_link(
    token: str,
    request: Request,
    event: str = Query(default="click", max_length=32),
    target: str = Query(default="", max_length=1024),
    duration_ms: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    message = (
        db.query(OutreachWhatsAppMessage)
        .filter(OutreachWhatsAppMessage.track_token == token)
        .first()
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Tracking link not found")
    base = _tracking_base(request)
    allowed_targets = {
        CATALOGUE_LINK: f"{base}/api/public/catalog/catalog",
        PROFILE_LINK: f"{base}/api/public/catalog/profile",
        WEBSITE_URL: WEBSITE_URL,
    }
    safe_target = allowed_targets.get(target, "")
    _apply_event(
        db,
        message=message,
        event_type=event,
        provider_event_id="",
        target_url=safe_target,
        duration_ms=duration_ms,
        meta={"token": token},
    )
    db.commit()
    if not safe_target:
        return {"ok": True, "event": event}
    return RedirectResponse(url=safe_target, status_code=302)


@router.get("/dashboard")
def engagement_dashboard(
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = _now() - timedelta(days=days)
    campaigns = (
        db.query(OutreachWhatsAppCampaign)
        .filter(OutreachWhatsAppCampaign.user_id == user.id)
        .all()
    )
    messages = (
        db.query(OutreachWhatsAppMessage)
        .filter(OutreachWhatsAppMessage.user_id == user.id, OutreachWhatsAppMessage.created_at >= since)
        .all()
    )
    message_ids = [m.id for m in messages]
    events = (
        db.query(OutreachEngagementEvent)
        .filter(OutreachEngagementEvent.user_id == user.id)
        .all()
    )
    events = [e for e in events if e.message_id in set(message_ids)]

    by_event: dict[str, int] = defaultdict(int)
    for event in events:
        by_event[event.event_type] += 1

    daily: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sent": 0, "delivered": 0, "read": 0, "failed": 0, "clicks": 0, "downloads": 0}
    )
    for message in messages:
        day = message.created_at.strftime("%Y-%m-%d")
        daily[day]["sent"] += 1 if message.sent_at else 0
        daily[day]["delivered"] += 1 if message.delivered_at else 0
        daily[day]["read"] += 1 if message.read_at else 0
        daily[day]["failed"] += 1 if message.failed_at else 0
    for event in events:
        day = event.occurred_at.strftime("%Y-%m-%d")
        if event.event_type in ("click", "product_link"):
            daily[day]["clicks"] += 1
        if event.event_type in ("catalog_download", "download"):
            daily[day]["downloads"] += 1

    contact_stats: dict[int, dict[str, Any]] = {}
    for message in messages:
        key = message.contact_id
        stat = contact_stats.setdefault(
            key,
            {
                "contact_id": key,
                "name": message.name,
                "company": message.company,
                "phone": message.phone,
                "sent": 0,
                "delivered": 0,
                "read": 0,
                "failed": 0,
                "clicks": 0,
                "engagement_ms": 0,
            },
        )
        stat["sent"] += 1 if message.sent_at else 0
        stat["delivered"] += 1 if message.delivered_at else 0
        stat["read"] += 1 if message.read_at else 0
        stat["failed"] += 1 if message.failed_at else 0
    for event in events:
        message = next((m for m in messages if m.id == event.message_id), None)
        if message is None:
            continue
        stat = contact_stats[message.contact_id]
        if event.event_type in ("click", "product_link"):
            stat["clicks"] += 1
        stat["engagement_ms"] += int(event.duration_ms or 0)

    totals = {
        "campaigns": len(campaigns),
        "sent": sum(1 for m in messages if m.sent_at),
        "delivered": sum(1 for m in messages if m.delivered_at),
        "read": sum(1 for m in messages if m.read_at),
        "failed": sum(1 for m in messages if m.failed_at),
        "link_clicks": by_event.get("click", 0) + by_event.get("product_link", 0),
        "catalog_downloads": by_event.get("catalog_download", 0) + by_event.get("download", 0),
        "landing_seconds": round(
            sum(e.duration_ms for e in events if e.event_type == "landing") / 1000, 1
        ),
    }
    sent_total = totals["sent"] or 0
    return {
        "days": days,
        "totals": totals,
        "rates": {
            "delivery_rate": round(
                ((sent_total - totals["failed"]) / sent_total) * 100, 1
            )
            if sent_total
            else 0.0,
            "read_rate": round((totals["read"] / sent_total) * 100, 1) if sent_total else 0.0,
            "click_rate": round((totals["link_clicks"] / sent_total) * 100, 1)
            if sent_total
            else 0.0,
            "catalog_open_rate": round((totals["catalog_downloads"] / sent_total) * 100, 1)
            if sent_total
            else 0.0,
        },
        "daily": [{"date": day, **values} for day, values in sorted(daily.items())],
        "campaigns": [_campaign_out(row) for row in campaigns],
        "contacts": sorted(contact_stats.values(), key=lambda row: (row["read"], row["clicks"]), reverse=True),
    }


@router.post("/import/sales-data")
def import_sales_data(
    files: list[UploadFile] = File(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    created = updated = skipped = 0
    sources: list[dict[str, Any]] = []

    for upload in files:
        data = upload.file.read()
        name = upload.filename or "upload"
        lower = name.lower()
        text = ""
        chat_name = ""
        if lower.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for info in archive.infolist():
                    if not info.filename.lower().endswith((".txt", ".md")):
                        continue
                    parsed = parse_whatsapp_chat(
                        archive.read(info.filename).decode("utf-8", errors="replace")
                    )
                    chat_name = re.sub(r"^WhatsApp Chat with\s+", "", Path(info.filename).stem)
                    text = " ".join(message["text"] for message in parsed["messages"])
                    break
            if not chat_name:
                chat_name = re.sub(r"\.zip$", "", name, flags=re.I)
        elif lower.endswith(".pdf"):
            text = _pdf_text(data)
            chat_name = re.sub(r"\.pdf$", "", name, flags=re.I)
        elif lower.endswith((".xlsx", ".xls", ".csv", ".json", ".vcf")):
            records = records_from_bytes(name, data)
            for record in records:
                company = (record.get("company") or "").strip()
                if not company:
                    skipped += 1
                    continue
                key = _company_key(company)
                existing = (
                    db.query(MarketingCompany)
                    .filter(MarketingCompany.user_id == user.id, MarketingCompany.company_key == key)
                    .first()
                )
                if existing is None:
                    db.add(
                        MarketingCompany(
                            user_id=user.id,
                            company=company,
                            company_key=key,
                            contact_name=(record.get("name") or "").strip(),
                            phone=(record.get("phone") or "").strip(),
                            email=(record.get("email") or "").strip(),
                            requirements=(record.get("requirements") or record.get("notes") or "").strip(),
                            marketing_approved=False,
                            source_reference=f"{name}",
                            source_file=name,
                            segment="imported",
                        )
                    )
                    created += 1
                else:
                    existing.requirements = record.get("requirements") or existing.requirements
                    existing.source_reference = f"{existing.source_reference} | {name}".strip(" |")
                    updated += 1
            sources.append({"file": name, "records": len(records)})
            continue
        else:
            skipped += 1
            sources.append({"file": name, "status": "unsupported"})
            continue

        phone = _phone(chat_name) or _phone(name)
        company = re.sub(r"\s*\(\d+\)\s*$", "", chat_name).strip() or name
        requirements = _requirements_from_text(text)
        if not requirements and not phone:
            skipped += 1
            sources.append({"file": name, "status": "no_contact_or_requirement"})
            continue
        key = _company_key(company)
        existing = (
            db.query(MarketingCompany)
            .filter(MarketingCompany.user_id == user.id, MarketingCompany.company_key == key)
            .first()
        )
        if existing is None and phone:
            existing = (
                db.query(MarketingCompany)
                .filter(MarketingCompany.user_id == user.id, MarketingCompany.phone.like(f"%{phone[-10:]}%"))
                .first()
            )
        if existing is None:
            db.add(
                MarketingCompany(
                    user_id=user.id,
                    company=company,
                    company_key=key,
                    phone=phone,
                    requirements=requirements,
                    marketing_approved=False,
                    source_reference=f"{name}",
                    source_file=name,
                    segment="imported",
                )
            )
            created += 1
        else:
            existing.requirements = requirements or existing.requirements
            existing.phone = existing.phone or phone
            existing.source_reference = f"{existing.source_reference} | {name}".strip(" |")
            existing.segment = existing.segment or "imported"
            updated += 1
        sources.append(
            {
                "file": name,
                "company": company,
                "phone": phone,
                "requirements_chars": len(requirements),
            }
        )

    db.commit()
    log_event(
        db,
        action="outreach.whatsapp.sales_import",
        actor_user_id=user.id,
        resource_type="marketing_company",
        detail={"files": len(files), "created": created, "updated": updated, "skipped": skipped},
        commit=True,
    )
    return {"created": created, "updated": updated, "skipped": skipped, "sources": sources}
