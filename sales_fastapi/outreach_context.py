"""Personalization context for Kalika outreach templates.

Contact fields come from the marketing/CRM record. Order and product details are
looked up from the synced Tally sales register first (it carries item names and
voucher numbers), then from the ERP order report. Nothing is entered manually by
the user; missing values are reported by ``render_resolved_report``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import ErpOrder, TallySale
from .outreach_forms import get_form_links, with_contact_context
from .templating import contact_context


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _short(value: Any, limit: int = 90) -> str:
    text = _text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _company_key(value: Any) -> str:
    return _text(value).lower()


def order_details_for_company(db: Session, company: str) -> dict[str, str]:
    """Latest order + product for a company from Tally, falling back to ERP orders."""
    key = _company_key(company)
    if not key:
        return {}

    sale = (
        db.query(TallySale)
        .filter(func.lower(func.trim(TallySale.buyer)) == key)
        .order_by(TallySale.sale_date.desc(), TallySale.id.desc())
        .first()
    )
    if sale is None and len(key) >= 4:
        sale = (
            db.query(TallySale)
            .filter(func.lower(func.trim(TallySale.buyer)).like(f"{key}%"))
            .order_by(TallySale.sale_date.desc(), TallySale.id.desc())
            .first()
        )

    if sale is not None:
        return {
            "order_number": _text(sale.voucher_no),
            "order_date": _text(sale.sale_date),
            "product_name": _short(sale.item_name),
            "order_value": str(sale.value or ""),
            "order_source": "tally",
        }

    order = (
        db.query(ErpOrder)
        .filter(func.lower(func.trim(ErpOrder.customer)) == key)
        .order_by(ErpOrder.order_date.desc(), ErpOrder.id.desc())
        .first()
    )
    if order is None and len(key) >= 4:
        order = (
            db.query(ErpOrder)
            .filter(func.lower(func.trim(ErpOrder.customer)).like(f"{key}%"))
            .order_by(ErpOrder.order_date.desc(), ErpOrder.id.desc())
            .first()
        )

    if order is not None:
        return {
            "order_number": _text(order.order_no),
            "order_date": _text(order.order_date),
            "product_name": "",
            "order_value": str(order.total_value or ""),
            "order_source": "erp",
        }
    return {}


def outreach_context(
    db: Session,
    contact: Any,
    *,
    company: str | None = None,
    requirements: str = "",
    category: str = "",
    cache: dict[str, dict[str, str]] | None = None,
    form_links: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a render context with contact, product, order and CTA-link values."""
    base = contact_context(contact)
    resolved_company = _text(company or base.get("company") or "")
    person = _text(base.get("contact_name"))
    phone = _text(base.get("phone"))
    letters = sum(ch.isalpha() for ch in person)
    digits = sum(ch.isdigit() for ch in person)
    if (
        not person
        or person == phone
        or (digits >= 6 and letters == 0)
        or person.lower() in {"n/a", "na", "none", "-", "not available"}
    ):
        person = resolved_company or "there"
        base["contact_name"] = person
        base["name"] = person
    order_cache = cache if cache is not None else {}
    cache_key = _company_key(resolved_company)
    if cache_key and cache_key in order_cache:
        order = order_cache[cache_key]
    else:
        order = order_details_for_company(db, resolved_company)
        if cache_key:
            order_cache[cache_key] = order

    hint = _short(requirements) or _short(base.get("context")) or _short(category)
    product = (
        order.get("product_name")
        or hint
        or _text(base.get("intent"))
        or "Kalika Enterprises packaging"
    )
    links = form_links if form_links is not None else get_form_links(db)
    context = {
        **base,
        "order_number": order.get("order_number", ""),
        "order_no": order.get("order_number", ""),
        "order_date": order.get("order_date", ""),
        "order_value": order.get("order_value", ""),
        "order_source": order.get("order_source", ""),
        "product_name": product,
        "product": product,
        "product_or_solution": product,
    }
    review_url = with_contact_context(links.get("review_url", ""), context)
    feedback_url = with_contact_context(links.get("feedback_url", ""), context)
    meeting_url = with_contact_context(links.get("meeting_url", ""), context)
    context.update(
        {
            "review_url": review_url,
            "review_link": review_url,
            "feedback_form_url": feedback_url,
            "feedback_url": feedback_url,
            "meeting_or_enquiry_url": meeting_url,
        }
    )
    return context
