"""Pure helpers for the feedback pipeline: templates, segments, phone handling,
message personalisation and wa.me links.

Kept dependency-free (stdlib only) so unit tests and cron scripts can use them
without the FastAPI/pandas stack.
"""

from __future__ import annotations

import re
from urllib.parse import quote

CATALOGUE_LINK = (
    "https://storage.googleapis.com/kalika_enterprises/ERP-V1/New_kalika_enterprises_catalog.pdf"
)
PROFILE_LINK = "https://storage.googleapis.com/kalika_enterprises/kalika%20backup/KALIKA.pdf"
POLY_CALC_LINK = "https://storage.googleapis.com/kalika_enterprises/sales-metadata/POLY%20BAG%20CALACULATION%20SHEET.xlsx"

RATE_BLOCK = (
    "Stretch film 23-51 mic: Rs.168/kg | VCI bags 50 mic: Rs.182/kg | "
    "Regular polybags: Rs.170-172/kg | Printed polybags: Rs.182/kg | "
    "BOPP tape 2in: Rs.30-32/pc | Hand gloves 40/60/80gm: Rs.6.50/8/9-9.50 per pc"
)

TEMPLATES = {
    "recent_orders": [
        {
            "id": "WA-ORD-01",
            "name": "Order status update",
            "intent": "retention",
            "text": "Namaste {name} ji, your Kalika Enterprises order {order_no} (Rs. {amount}) status: {status}. "
            "Reply here for any change in quantity or delivery schedule. - {agent}",
        },
        {
            "id": "WA-FBK-02",
            "name": "Delivery feedback ask",
            "intent": "feedback",
            "text": "Namaste {name} ji, how was your recent Kalika delivery (order {order_no})? "
            "Reply: 1 On time | 2 Late | 3 Not received | 4 Delivery-team feedback. 10 seconds only. Thank you!",
        },
        {
            "id": "WA-FBK-06",
            "name": "Satisfaction + reorder nudge",
            "intent": "feedback",
            "text": "Namaste {name} ji, thank you for your recent order {order_no} with Kalika Enterprises. "
            "Rate your experience 1-5 by replying to this message. Need repeat stock? "
            "Current rates: {rates}. - {agent}",
        },
    ],
    "new_customers": [
        {
            "id": "WA-NEW-01",
            "name": "Welcome first touch",
            "intent": "acquisition",
            "text": "Namaste {name} ji, this is {agent} from Kalika Enterprises, Ahmednagar - manufacturer of "
            "stretch/shrink film, BOPP & masking tape, VCI bags, tarpaulin, HDPE/poly bags and knitted gloves. "
            "Company profile: {profile_link}. Any current packaging requirement at {company}?",
        },
        {
            "id": "WA-NEW-02",
            "name": "Welcome + catalogue",
            "intent": "acquisition",
            "text": "Namaste {name} ji, welcome to Kalika Enterprises! Our product catalogue: {catalogue_link}. "
            "Popular rates: {rates}. Reply with your requirement for a same-day quotation. - {agent}",
        },
        {
            "id": "WA-FBK-01",
            "name": "Feedback menu (welcome)",
            "intent": "feedback",
            "text": "Hello from Kalika Enterprises! How can we help you today? Reply: 1 Product catalogue | "
            "2 Check delivery | 3 Share feedback | 4 Report issue | 5 Talk to our team. Your feedback matters!",
        },
    ],
    "leads": [
        {
            "id": "WA-FU-01",
            "name": "Follow-up: not answered",
            "intent": "re-engagement",
            "text": "Namaste {name} ji, {agent} from Kalika Enterprises (Ahmednagar). Tried calling about packaging "
            "materials - stretch film, BOPP tape, VCI bags, polybags. Catalogue: {catalogue_link}. "
            "Reply YES for a callback or send your requirement here.",
        },
        {
            "id": "WA-FU-02",
            "name": "Follow-up: busy / call later",
            "intent": "re-engagement",
            "text": "Namaste {name} ji, following up as requested. Kalika Enterprises - {rates}. "
            "Rate list & catalogue: {catalogue_link}. When can I call for 2 minutes?",
        },
        {
            "id": "WA-FU-03",
            "name": "Follow-up: details sent",
            "intent": "nurture",
            "text": "Namaste {name} ji, earlier we shared Kalika Enterprises product details. Need current rates or "
            "samples for {product}? Polybag calculation sheet: {poly_link}. Happy to send a quotation today.",
        },
        {
            "id": "WA-RT-01",
            "name": "Rate share",
            "intent": "conversion",
            "text": "Namaste {name} ji, current Kalika rates - {rates}. GST extra. "
            "Order on WhatsApp or reply for a proforma invoice. - {agent}",
        },
        {
            "id": "WA-EXP-01",
            "name": "Expo follow-up (Packvision)",
            "intent": "re-engagement",
            "text": "Namaste {name} ji, thank you for connecting with Kalika Enterprises at Packvision. As discussed, "
            "catalogue + rates: {catalogue_link}. Can we send samples of {product} this week?",
        },
    ],
}

SEGMENT_META = {
    "recent_orders": {
        "label": "Recent orders",
        "source": "ERP-V1 latest report (Orders sheet)",
        "description": "Customers with live/recent orders - delivery feedback & order updates.",
    },
    "new_customers": {
        "label": "New customers",
        "source": "contacts DB (GCS sync, last 7 days)",
        "description": "Freshly synced contacts - welcome + catalogue + first feedback.",
    },
    "leads": {
        "label": "Leads",
        "source": "contacts DB (call-status / requirement notes)",
        "description": "Marketing-list leads with call outcomes - follow-up & rate sharing.",
    },
}


def norm_phone(raw: str) -> str:
    """Normalise to wa.me digits: 10-digit IN numbers get the 91 prefix.

    Landlines (leading 0, e.g. 020 2605 2352) are rejected — they cannot
    receive WhatsApp messages via wa.me.
    """
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0"):
        return ""
    if len(digits) == 10:
        digits = "91" + digits
    return digits if 11 <= len(digits) <= 15 else ""


def first_phone(raw: str) -> str:
    """First phone-looking token out of a (possibly multi-number) field."""
    for part in re.split(r"[,;/\n]", raw or ""):
        p = norm_phone(part)
        if p:
            return p
    return ""


def fill(
    template: str,
    *,
    name="",
    company="",
    agent="Team Kalika",
    order_no="",
    amount="",
    status="",
    product="packaging materials",
    rates=RATE_BLOCK,
) -> str:
    return (
        template.replace("{name}", name or "Sir/Madam")
        .replace("{company}", company or "your company")
        .replace("{agent}", agent)
        .replace("{order_no}", order_no or "-")
        .replace("{amount}", amount or "-")
        .replace("{status}", status or "in process")
        .replace("{product}", product)
        .replace("{rates}", rates)
        .replace("{catalogue_link}", CATALOGUE_LINK)
        .replace("{profile_link}", PROFILE_LINK)
        .replace("{poly_link}", POLY_CALC_LINK)
    )


def wa_link(phone: str, message: str) -> str:
    return f"https://wa.me/{phone}?text={quote(message)}"
