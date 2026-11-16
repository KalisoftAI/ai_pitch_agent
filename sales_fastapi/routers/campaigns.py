"""Bulk outreach campaigns with human-in-the-loop review.



Flow: create (render + optional Gemma personalisation) -> pending_review ->

approve / edit -> send (email / WhatsApp / WeChat) -> status updates.

"""

from __future__ import annotations

import re
from datetime import datetime
from functools import lru_cache
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..llm.router import ModelRouter
from ..models import (
    Campaign,
    CampaignMessage,
    Contact,
    EmailConnection,
    MarketingCompany,
    MessageTemplate,
    User,
)
from ..outreach_context import outreach_context
from ..schemas import (
    CampaignCreate,
    CampaignDetail,
    CampaignMessageOut,
    CampaignMessageUpdate,
    CampaignOut,
    CampaignSendResult,
)
from ..security import get_current_user
from ..services import MailSender
from ..templating import contact_context, looks_html, render_resolved
from ..wechaty import WechatyGateway

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _valid_email(value: str | None) -> bool:
    return bool(_EMAIL_RE.fullmatch((value or "").strip()))


def _valid_phone(value: str | None) -> bool:
    return len(re.sub(r"\D", "", value or "")) >= 8


SENDER_CONTEXT = {
    "sender_name": "Kalisoft AI",
    "sender_email": "ai.solutions@kalisoftai.in",
    "product": "Kalisoft AI Sales Automation",
    "product_name": "Kalisoft AI Sales Automation",
    "calendar_link": "https://kalisoftai.in/demo",
}


@lru_cache
def _llm_router() -> ModelRouter:

    return ModelRouter()


def _ai_personalise(template: MessageTemplate, contact: Contact, channel: str) -> tuple[str, str]:
    """Return (model_name, body). Falls back to the template render on any failure."""

    base_body = render_resolved(template.body, {**SENDER_CONTEXT, **contact_context(contact)})

    if not settings.LLM_ENABLED:
        return ("template", base_body)

    prompt = (
        f"Write a concise {channel} outreach message for a B2B sales campaign.\n"
        f"Strategy: {template.strategy}. Funnel stage: {template.funnel_stage}.\n"
        f"Recipient: {contact.name or 'decision maker'} at {contact.company or 'the company'}.\n"
        f"Intent: {contact.intent or 'general'}. Context: {contact.context or ''}.\n"
        f"Product: {SENDER_CONTEXT['product']}. Sender: {SENDER_CONTEXT['sender_name']}.\n\n"
        f"Base draft to personalise (keep under 120 words):\n{base_body}\n\n"
        "Return only the final message body."
    )

    try:
        route = _llm_router().run(
            "generate_outreach_message", prompt, system="You are a precise B2B sales copywriter."
        )

        text = route.result.text.strip()

        if route.result.provider == "echo" or not text:
            return ("template", base_body)

        return (route.result.model, text)

    except Exception:  # noqa: BLE001 - fall back to the template
        return ("template", base_body)


@router.post("", response_model=CampaignDetail, status_code=201)
def create_campaign(
    payload: CampaignCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    template = (
        db.query(MessageTemplate)
        .filter(
            MessageTemplate.id == payload.template_id, MessageTemplate.user_id.in_([user.id, 0])
        )
        .first()
    )

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    phone_channel = payload.channel in {"whatsapp", "wechat"}

    if payload.filter.contact_ids:
        contact_ids = list(dict.fromkeys(int(x) for x in payload.filter.contact_ids if x))

        if payload.filter.contact_type == "marketing_companies":
            records = (
                db.query(MarketingCompany)
                .filter(MarketingCompany.user_id == user.id, MarketingCompany.id.in_(contact_ids))
                .order_by(MarketingCompany.company.asc())
                .all()
            )

            contacts = [
                SimpleNamespace(
                    id=record.id,
                    company=record.company,
                    name=record.contact_name,
                    email=record.email,
                    phone=record.phone,
                    intent=record.category,
                    domain="",
                    context=record.requirements,
                )
                for record in records
                if (_valid_phone(record.phone) if phone_channel else _valid_email(record.email))
            ]

        else:
            contacts = (
                db.query(Contact)
                .filter(Contact.user_id == user.id, Contact.id.in_(contact_ids))
                .order_by(Contact.created_at.desc())
                .all()
            )

            if phone_channel:
                contacts = [c for c in contacts if _valid_phone(c.phone)]

            else:
                contacts = [c for c in contacts if _valid_email(c.email)]

    elif payload.filter.contact_type == "marketing_companies":
        query = db.query(MarketingCompany).filter(MarketingCompany.user_id == user.id)

        if payload.filter.category:
            query = query.filter(MarketingCompany.category.ilike(f"%{payload.filter.category}%"))

        if payload.filter.call_status:
            query = query.filter(
                MarketingCompany.call_status.ilike(f"%{payload.filter.call_status}%")
            )

        if payload.filter.funnel_stage:
            query = query.filter(MarketingCompany.funnel_stage == payload.filter.funnel_stage)

        if payload.filter.q:
            like = f"%{payload.filter.q}%"

            query = query.filter(
                MarketingCompany.company.ilike(like)
                | MarketingCompany.contact_name.ilike(like)
                | MarketingCompany.email.ilike(like)
                | MarketingCompany.phone.ilike(like)
                | MarketingCompany.requirements.ilike(like)
            )

        address_field = MarketingCompany.phone if phone_channel else MarketingCompany.email

        records = (
            query.filter(address_field != "")
            .order_by(MarketingCompany.company.asc())
            .limit(payload.filter.limit)
            .all()
        )

        contacts = [
            SimpleNamespace(
                id=record.id,
                company=record.company,
                name=record.contact_name,
                email=record.email,
                phone=record.phone,
                intent=record.category,
                domain="",
                context=record.requirements,
            )
            for record in records
            if (_valid_phone(record.phone) if phone_channel else _valid_email(record.email))
        ]

    else:
        query = db.query(Contact).filter(Contact.user_id == user.id)

        if payload.filter.intent:
            query = query.filter(Contact.intent == payload.filter.intent)

        if payload.filter.source:
            query = query.filter(Contact.source == payload.filter.source)

        if payload.filter.q:
            like = f"%{payload.filter.q}%"

            query = query.filter(
                Contact.company.ilike(like) | Contact.name.ilike(like) | Contact.email.ilike(like)
            )

        address_field = Contact.phone if phone_channel else Contact.email

        contacts = (
            query.filter(address_field != "")
            .order_by(Contact.created_at.desc())
            .limit(payload.filter.limit)
            .all()
        )

    if not contacts:
        raise HTTPException(status_code=400, detail="No contacts matched the campaign filter")

    # --- Channel format compatibility: never auto-convert, never send incompatible formats ---

    if payload.channel in {"whatsapp", "wechat"}:
        _body_src = payload.body_override if payload.body_override is not None else template.body

        if looks_html(_body_src or ""):
            raise HTTPException(
                status_code=400,
                detail=(
                    "WhatsApp messages must be plain text. The selected content is HTML and is never "
                    "converted automatically - pick an existing WhatsApp template, or write and save a "
                    "WhatsApp-specific plain-text version, then confirm before sending."
                ),
            )

        if (
            not (_body_src or "").strip()
            and payload.body_override is None
            and not (template.body or "").strip()
        ):
            raise HTTPException(
                status_code=400,
                detail="WhatsApp message text is missing - add a plain-text message before sending.",
            )

    campaign = Campaign(
        user_id=user.id,
        name=payload.name,
        channel=payload.channel,
        strategy=payload.strategy,
        template_id=template.id,
        image_url=payload.image_url or "",
        status="pending_review",
        total=len(contacts),
    )

    db.add(campaign)

    db.commit()

    db.refresh(campaign)

    image_url = (payload.image_url or "").strip()

    video_url = (payload.video_url or "").strip()

    if image_url and payload.channel == "email":
        image_block = (
            f'<div style="margin:12px 0"><img src="{image_url}" '
            'alt="Kalika Enterprises" style="max-width:100%;width:520px;border-radius:10px;display:block"/></div>'
        )

    else:
        image_block = f"\n\n🖼️ {image_url}" if image_url else ""

    if video_url and payload.channel == "email":
        video_block = (
            f'<div style="margin:12px 0"><a href="{video_url}" '
            'style="display:inline-block;background:#10251f;color:#fff;text-decoration:none;'
            'padding:10px 16px;border-radius:8px;font-weight:600">▶ Watch our video</a></div>'
        )

    else:
        video_block = f"\n\n🎬 {video_url}" if video_url else ""

    catalog_url = (payload.catalog_url or "").strip()

    if catalog_url and payload.channel == "email":
        catalog_block = (
            '\n<div style="margin:12px 0"><a href="' + catalog_url + '" '
            'style="display:inline-block;background:#2b56a3;color:#fff;text-decoration:none;'
            'padding:10px 16px;border-radius:8px;font-weight:600">Download our catalogue (PDF)</a></div>'
        )

    else:
        catalog_block = ("\n\nCatalogue: " + catalog_url) if catalog_url else ""

    model_used = "template"

    subject_src = (
        payload.subject_override if payload.subject_override is not None else template.subject
    )

    body_src = payload.body_override if payload.body_override is not None else template.body

    order_cache: dict[str, dict[str, str]] = {}

    for contact in contacts:
        render_context = {
            **SENDER_CONTEXT,
            **outreach_context(db, contact, cache=order_cache),
        }

        subject = render_resolved(subject_src, render_context)

        if payload.use_ai and payload.body_override is None:
            model_name, body = _ai_personalise(template, contact, payload.channel)

            body = render_resolved(body, render_context)

        else:
            model_name, body = "template", render_resolved(body_src, render_context)

        if model_name != "template":
            model_used = model_name

        final_body = body

        if image_block:
            if payload.channel == "email" and ("<body" in (body or "").lower()):
                final_body = body.replace("</body>", image_block + "</body>", 1)

            else:
                final_body = (body or "") + image_block

        if video_block:
            if payload.channel == "email" and ("</body>" in (final_body or "").lower()):
                final_body = final_body.replace("</body>", video_block + "</body>", 1)

            else:
                final_body = (final_body or "") + video_block

        if catalog_block:
            if payload.channel == "email" and ("</body>" in (final_body or "").lower()):
                final_body = final_body.replace("</body>", catalog_block + "</body>", 1)

            else:
                final_body = (final_body or "") + catalog_block

        db.add(
            CampaignMessage(
                campaign_id=campaign.id,
                user_id=user.id,
                contact_id=contact.id,
                contact_name=(getattr(contact, "name", "") or ""),
                to_address=contact.phone if phone_channel else contact.email,
                rendered_subject=subject,
                rendered_body=final_body,
                image_url=image_url,
                status="pending_review",
            )
        )

    campaign.ai_model = model_used if payload.use_ai else "template"

    db.commit()

    db.refresh(campaign)

    log_event(
        db,
        action="campaign.create",
        actor_user_id=user.id,
        resource_type="campaign",
        resource_id=str(campaign.id),
        tenant_id=user.domain,
        ip_address=request.client.host if request.client else "",
        detail={"channel": payload.channel, "total": campaign.total, "ai_model": campaign.ai_model},
        commit=True,
    )

    if payload.auto_send and campaign.total:
        db.query(CampaignMessage).filter(
            CampaignMessage.campaign_id == campaign.id,
            CampaignMessage.status == "pending_review",
        ).update({"status": "approved"}, synchronize_session=False)

        campaign.status = "approved"

        db.commit()

        send_campaign(campaign.id, request, user, db)

        db.refresh(campaign)

    return _detail(db, campaign)


def _detail(db: Session, campaign: Campaign) -> CampaignDetail:

    messages = (
        db.query(CampaignMessage)
        .filter(CampaignMessage.campaign_id == campaign.id)
        .order_by(CampaignMessage.id.asc())
        .limit(1000)
        .all()
    )

    opened = sum(1 for m in messages if m.status == "opened")

    data = CampaignOut.model_validate(campaign).model_dump()

    data.pop("opened_count", None)

    return CampaignDetail(
        **data,
        opened_count=opened,
        messages=[CampaignMessageOut.model_validate(message) for message in messages],
    )


@router.get("", response_model=list[CampaignOut])
def list_campaigns(user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    return (
        db.query(Campaign)
        .filter(Campaign.user_id == user.id)
        .order_by(Campaign.created_at.desc())
        .all()
    )


@router.get("/analytics")
def campaign_analytics(
    days: int = Query(default=14, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real outreach analytics aggregated from campaign/message records (no fabricated counts)."""
    from collections import defaultdict
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(days=days - 1)
    campaigns = (
        db.query(Campaign)
        .filter(Campaign.user_id == user.id, Campaign.created_at >= since)
        .order_by(Campaign.created_at.desc())
        .all()
    )
    campaign_ids = [c.id for c in campaigns]
    opened_map: dict[int, int] = {}
    pending_map: dict[int, int] = {}
    if campaign_ids:
        for cid, count in (
            db.query(CampaignMessage.campaign_id, func.count(CampaignMessage.id))
            .filter(
                CampaignMessage.campaign_id.in_(campaign_ids), CampaignMessage.status == "opened"
            )
            .group_by(CampaignMessage.campaign_id)
            .all()
        ):
            opened_map[cid] = int(count)
        for cid, count in (
            db.query(CampaignMessage.campaign_id, func.count(CampaignMessage.id))
            .filter(
                CampaignMessage.campaign_id.in_(campaign_ids),
                CampaignMessage.status.in_(("pending_review", "approved", "queued")),
            )
            .group_by(CampaignMessage.campaign_id)
            .all()
        ):
            pending_map[cid] = int(count)

    by_day: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "email_sent": 0,
            "whatsapp_sent": 0,
            "sent": 0,
            "failed": 0,
            "opened": 0,
            "pending": 0,
        }
    )
    by_channel: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sent": 0, "failed": 0, "opened": 0, "pending": 0, "campaigns": 0}
    )
    totals = {
        "email_sent": 0,
        "whatsapp_sent": 0,
        "sent": 0,
        "failed": 0,
        "opened": 0,
        "pending": 0,
        "campaigns": len(campaigns),
    }
    by_campaign = []
    for campaign in campaigns:
        channel = (campaign.channel or "email").lower()
        day = str(campaign.created_at)[:10] if campaign.created_at else "unknown"
        sent = int(campaign.sent_count or 0)
        failed = int(campaign.failed_count or 0)
        opened = opened_map.get(campaign.id, 0)
        pending = pending_map.get(campaign.id, 0)
        key = "email_sent" if channel == "email" else "whatsapp_sent"
        for bucket in (by_day[day], by_channel[channel]):
            bucket["sent"] += sent
            bucket["failed"] += failed
            bucket["opened"] += opened
            bucket["pending"] += pending
        by_day[day][key] += sent
        by_channel[channel]["campaigns"] += 1
        totals["sent"] += sent
        totals["failed"] += failed
        totals["opened"] += opened
        totals["pending"] += pending
        totals[key] += sent
        by_campaign.append(
            {
                "id": campaign.id,
                "name": campaign.name,
                "channel": channel,
                "status": campaign.status,
                "total": campaign.total,
                "sent": sent,
                "failed": failed,
                "opened": opened,
                "pending": pending,
                "day": day,
            }
        )

    by_group: dict[str, dict[str, int]] = defaultdict(lambda: {"sent": 0, "failed": 0, "opened": 0})
    try:
        msg_rows = (
            db.query(MarketingCompany.category, CampaignMessage.status)
            .join(CampaignMessage, CampaignMessage.contact_id == MarketingCompany.id)
            .filter(
                CampaignMessage.user_id == user.id,
                CampaignMessage.sent_at.isnot(None),
                CampaignMessage.sent_at >= since,
            )
            .all()
        )
        for category, status in msg_rows:
            group = (category or "Uncategorized").strip() or "Uncategorized"
            if status in ("sent", "opened"):
                by_group[group]["sent"] += 1
            if status == "failed":
                by_group[group]["failed"] += 1
            if status == "opened":
                by_group[group]["opened"] += 1
    except Exception:  # noqa: BLE001 - analytics must never break the dashboard
        by_group = defaultdict(lambda: {"sent": 0, "failed": 0, "opened": 0})

    return {
        "days": days,
        "generated_at": datetime.utcnow().isoformat(),
        "totals": totals,
        "by_channel": [{"channel": key, **value} for key, value in sorted(by_channel.items())],
        "by_campaign": by_campaign[:25],
        "by_group": [
            {"group": key, **value}
            for key, value in sorted(
                by_group.items(), key=lambda item: -(item[1]["sent"] + item[1]["failed"])
            )[:15]
        ],
        "daily": [{"day": day, **value} for day, value in sorted(by_day.items())],
        "note": (
            f"Real campaign/message records for the last {days} days. "
            "Sent = provider accepted; Opened = tracking-pixel hits; Pending = awaiting review/send."
        ),
    }


@router.get("/{campaign_id}", response_model=CampaignDetail)
def get_campaign(
    campaign_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):

    campaign = (
        db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    )

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return _detail(db, campaign)


@router.patch("/{campaign_id}/messages/{message_id}", response_model=CampaignMessageOut)
def edit_message(
    campaign_id: int,
    message_id: int,
    payload: CampaignMessageUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    message = (
        db.query(CampaignMessage)
        .filter(
            CampaignMessage.id == message_id,
            CampaignMessage.campaign_id == campaign_id,
            CampaignMessage.user_id == user.id,
        )
        .first()
    )

    if message is None:
        raise HTTPException(status_code=404, detail="Campaign message not found")

    if payload.rendered_subject is not None:
        message.rendered_subject = payload.rendered_subject

    if payload.rendered_body is not None:
        message.rendered_body = payload.rendered_body

    if payload.approve:
        message.status = "approved"

    db.commit()

    db.refresh(message)

    return message


@router.post("/{campaign_id}/approve", response_model=CampaignDetail)
def approve_campaign(
    campaign_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):

    campaign = (
        db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    )

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    db.query(CampaignMessage).filter(
        CampaignMessage.campaign_id == campaign_id, CampaignMessage.status == "pending_review"
    ).update({"status": "approved"}, synchronize_session=False)

    campaign.status = "approved"

    db.commit()

    db.refresh(campaign)

    log_event(
        db,
        action="campaign.approve",
        actor_user_id=user.id,
        resource_type="campaign",
        resource_id=str(campaign.id),
        tenant_id=user.domain,
        detail={},
        commit=True,
    )

    return _detail(db, campaign)


@router.post("/{campaign_id}/send", response_model=CampaignSendResult)
def send_campaign(
    campaign_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    campaign = (
        db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    )

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    messages = (
        db.query(CampaignMessage)
        .filter(CampaignMessage.campaign_id == campaign_id, CampaignMessage.status == "approved")
        .all()
    )

    sent = failed = skipped = 0

    email_connection = (
        db.query(EmailConnection)
        .filter(EmailConnection.user_id == user.id)
        .order_by(EmailConnection.is_connected.desc(), EmailConnection.id.asc())
        .first()
    )

    gateway = WechatyGateway()

    for message in messages:
        try:
            if campaign.channel == "email":
                if email_connection is None:
                    raise RuntimeError("no email connection configured")

                from ..security import decrypt_secret

                base_url = str(request.base_url).rstrip("/")

                track_url = f"{base_url}/api/campaigns/{campaign.id}/open/{message.id}"

                body_html = message.rendered_body or ""

                pixel = (
                    f'<img src="{track_url}" width="1" height="1" style="display:none;" alt="" />'
                )

                if "<html" in body_html.lower() or "<body" in body_html.lower():
                    body_html = (
                        body_html.replace("</body>", pixel + "</body>")
                        if "</body>" in body_html.lower()
                        else body_html + pixel
                    )

                MailSender(
                    email_connection.smtp_host,
                    email_connection.smtp_port,
                    email_connection.email_address,
                    decrypt_secret(email_connection.secret_encrypted),
                ).send(
                    message.to_address,
                    message.rendered_subject or campaign.name,
                    body_html,
                )

                message.status = "sent"

                sent += 1

            elif campaign.channel in {"whatsapp", "wechat"}:
                if looks_html(message.rendered_body or ""):
                    message.status = "failed"

                    message.error = "Incompatible format: HTML content cannot be sent to WhatsApp"

                    failed += 1

                    continue

                if not settings.WHATSAPP_ENABLED:
                    raise RuntimeError("WhatsApp/WeChat channel is disabled")

                result = gateway.send_text(message.to_address, message.rendered_body)

                message.status = "sent"

                message.provider_id = str(result.get("id", ""))

                sent += 1

            else:  # linkedin -> manual queue
                message.status = "queued"

                skipped += 1

            message.sent_at = datetime.utcnow()

        except Exception as exc:  # noqa: BLE001 - record per-message failure
            message.status = "failed"

            message.error = str(exc)[:500]

            failed += 1

    db.commit()  # persist per-message statuses before recomputing rollup counts

    campaign.sent_count = (
        db.query(CampaignMessage)
        .filter(
            CampaignMessage.campaign_id == campaign.id,
            CampaignMessage.status.in_(["sent", "opened"]),
        )
        .count()
    )

    campaign.failed_count = (
        db.query(CampaignMessage)
        .filter(CampaignMessage.campaign_id == campaign.id, CampaignMessage.status == "failed")
        .count()
    )

    processed = campaign.sent_count + campaign.failed_count

    if processed >= campaign.total:
        campaign.status = "completed" if campaign.failed_count == 0 else "failed"

    else:
        campaign.status = "partial"

    db.commit()

    db.refresh(campaign)

    log_event(
        db,
        action="campaign.send",
        actor_user_id=user.id,
        resource_type="campaign",
        resource_id=str(campaign.id),
        status=campaign.status,
        tenant_id=user.domain,
        detail={"sent": sent, "failed": failed, "skipped": skipped},
        commit=True,
    )

    return CampaignSendResult(
        campaign_id=campaign.id, status=campaign.status, sent=sent, failed=failed, skipped=skipped
    )


@router.post("/{campaign_id}/retry", response_model=CampaignSendResult)
def retry_failed(
    campaign_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-queue and re-send only the FAILED messages of a campaign."""

    campaign = (
        db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    )

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    flipped = (
        db.query(CampaignMessage)
        .filter(CampaignMessage.campaign_id == campaign_id, CampaignMessage.status == "failed")
        .update({"status": "approved", "error": ""}, synchronize_session=False)
    )

    if not flipped:
        return CampaignSendResult(
            campaign_id=campaign.id, status=campaign.status, sent=0, failed=0, skipped=0
        )

    db.commit()

    return send_campaign(campaign_id, request, user, db)


@router.post("/preview")
def preview_message(
    payload: CampaignCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Render personalized subject/body for a set of contacts without persisting/sending.



    Returns one resolved preview per contact so the UI can verify before sending.

    No placeholders are left unresolved in the returned content.

    """

    template = (
        db.query(MessageTemplate)
        .filter(MessageTemplate.id == payload.template_id, MessageTemplate.user_id == user.id)
        .first()
    )

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    phone_channel = payload.channel in {"whatsapp", "wechat"}

    if payload.filter.contact_ids:
        contact_ids = list(dict.fromkeys(int(x) for x in payload.filter.contact_ids if x))

        if payload.filter.contact_type == "marketing_companies":
            records = (
                db.query(MarketingCompany)
                .filter(MarketingCompany.user_id == user.id, MarketingCompany.id.in_(contact_ids))
                .order_by(MarketingCompany.company.asc())
                .all()
            )

            contacts = [
                SimpleNamespace(
                    id=r.id,
                    company=r.company,
                    name=r.contact_name,
                    email=r.email,
                    phone=r.phone,
                    intent=r.category,
                    domain="",
                    context=r.requirements,
                )
                for r in records
            ]

        else:
            contacts = (
                db.query(Contact)
                .filter(Contact.user_id == user.id, Contact.id.in_(contact_ids))
                .order_by(Contact.created_at.desc())
                .all()
            )

    else:
        contacts = []

    previews = []

    subject_src = (payload.subject_override or template.subject or "").strip()

    body_src = (payload.body_override or template.body or "").strip()

    order_cache: dict[str, dict[str, str]] = {}

    for c in contacts[:50]:
        to_addr = (c.phone if phone_channel else c.email) or ""

        ctx = {**SENDER_CONTEXT, **outreach_context(db, c, cache=order_cache)}

        subj = render_resolved(subject_src, ctx)

        body = render_resolved(body_src, ctx)

        previews.append(
            {
                "contact_id": c.id,
                "contact_name": getattr(c, "name", "") or getattr(c, "contact_name", "") or "",
                "company": getattr(c, "company", "") or "",
                "to_address": to_addr,
                "email": getattr(c, "email", "") or "",
                "phone": getattr(c, "phone", "") or "",
                "subject": subj,
                "body": body,
                "has_unresolved": "{{" in subj or "{{" in body,
                "channel_ok": bool(to_addr),
            }
        )

    return {"channel": payload.channel, "count": len(previews), "previews": previews}


@router.get("/{campaign_id}/open/{message_id}")
def mark_opened(campaign_id: int, message_id: int, db: Session = Depends(get_db)):

    from fastapi.responses import Response

    message = (
        db.query(CampaignMessage)
        .filter(CampaignMessage.id == message_id, CampaignMessage.campaign_id == campaign_id)
        .first()
    )

    if message is not None and message.status in {"sent", "opened"}:
        message.status = "opened"

        message.opened_at = datetime.utcnow()

        db.commit()

    pixel = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
    )

    return Response(content=pixel, media_type="image/png")


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):

    campaign = (
        db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    )

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    db.query(CampaignMessage).filter(CampaignMessage.campaign_id == campaign_id).delete(
        synchronize_session=False
    )

    db.delete(campaign)

    db.commit()
