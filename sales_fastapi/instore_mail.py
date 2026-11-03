"""Instore mail intelligence.

Pipeline
--------
mailbox (Gmail API / IMAP / existing interaction dump)
    -> normalized mail records (sender, intent, attachments, contact link)
    -> insights JSON (KPIs, missing links, graph nodes/edges, accuracy)
    -> local cache (gcs_data/instore_mails.json) + GCS snapshot.

The module is deliberately dependency-free apart from the app services so it can
run from the API, the nightly scheduler, and the offline refinement script.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Iterable

from .config import settings
from .services import GCSStorage, infer_intent

SNAPSHOT_NAME = "instore_mails.json"
_HIGH_INTENTS = {"quote_request", "order", "payment", "complaint", "meeting_request"}
_FILE_RE = re.compile(
    r"([A-Za-z0-9][A-Za-z0-9 _.-]{0,80}\.(?:pdf|xlsx?|docx?|csv|png|jpe?g|zip|dwg|dxf))",
    re.IGNORECASE,
)
_INTENT_EXTRA = (
    ("order", ("purchase order", "order loc", "order no", " po ", "po_", "po-", "dispatch")),
    ("payment", ("invoice", "payment", "proforma", "outstanding", "credit note")),
    ("quote_request", ("quotation", "quote", "rfq", "enquiry", "inquiry", "rate sheet", "price")),
    ("complaint", ("complaint", "damaged", "reject", "quality issue", "short supply")),
    ("meeting_request", ("meeting", "visit", "discuss", "call on", "appointment")),
)
_ATTACHMENT_HINTS = (
    "attach",
    "enclosed",
    "please find",
    "pfa",
    "sharing",
    "quotation",
    "rate sheet",
    "drawing",
    "specification",
    "purchase order",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def snapshot_path(path: str | Path | None = None) -> Path:
    return Path(path or settings.INSTORE_MAIL_CACHE_PATH)


def _sender(value: str) -> tuple[str, str, str]:
    name, address = parseaddr(value or "")
    email = (address or "").strip().lower()
    if not email and "@" in (value or ""):
        email = value.strip().lower()
    if not name:
        name = email.split("@")[0] if email else (value or "unknown")
    domain = email.split("@", 1)[1] if "@" in email else ""
    return name.strip(), email, domain


def _intent(subject: str, body: str, fallback: str = "") -> str:
    text = f" {subject} {body} ".lower()
    for intent, needles in _INTENT_EXTRA:
        if any(needle in text for needle in needles):
            return intent
    mapped = {
        "sales": "quote_request",
        "procurement": "procurement",
        "support": "complaint",
        "partnership": "partnership",
        "hiring": "hiring",
    }
    return mapped.get(fallback or infer_intent(text), fallback or "general")


def _attachment_purpose(name: str, subject: str, body: str) -> str:
    text = f"{name} {subject} {body}".lower()
    name_text = name.lower()
    suffix = Path(name).suffix.lower()
    if any(word in name_text for word in ("rate", "quotation", "quote", "price")):
        return "quote_or_rate_sheet"
    if any(word in name_text for word in ("po_", "po-", "purchase order")):
        return "purchase_order"
    if any(word in name_text for word in ("invoice", "payment", "proforma")):
        return "invoice_or_payment"
    if "drawing" in name_text or suffix in {".dwg", ".dxf"}:
        return "drawing_or_spec"
    if any(word in text for word in ("purchase order", " po ", "po_", "po-")):
        return "purchase_order"
    if any(word in text for word in ("invoice", "payment advice", "proforma")):
        return "invoice_or_payment"
    if "drawing" in text:
        return "drawing_or_spec"
    if any(word in text for word in ("rate", "quotation", "quote", "price")):
        return "quote_or_rate_sheet"
    if suffix in {".png", ".jpg", ".jpeg"}:
        return "image_reference"
    if suffix in {".xls", ".xlsx", ".csv"}:
        return "data_sheet"
    return "document"


def _infer_attachments(mail: dict[str, Any]) -> list[dict[str, Any]]:
    subject = str(mail.get("subject", ""))
    body = str(mail.get("snippet") or mail.get("body") or "")
    found: list[dict[str, Any]] = []
    for item in mail.get("attachments") or []:
        if isinstance(item, str):
            item = {"name": item}
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        found.append(
            {
                "name": name,
                "mime_type": str(item.get("mime_type", "")),
                "size_bytes": int(item.get("size") or item.get("size_bytes") or 0),
                "purpose": item.get("purpose")
                or _attachment_purpose(name, subject, body),
            }
        )
    if found:
        return found
    text = f"{subject}\n{body}"
    if not any(hint in text.lower() for hint in _ATTACHMENT_HINTS):
        return []
    names = list(dict.fromkeys(match.strip() for match in _FILE_RE.findall(text)))
    return [
        {"name": name, "mime_type": "", "size_bytes": 0, "purpose": _attachment_purpose(name, subject, body)}
        for name in names[:6]
    ]


def _phone_key(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 10 else digits


def _contact_index(contacts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    by_email: dict[str, dict[str, Any]] = {}
    by_domain: dict[str, dict[str, Any]] = {}
    by_company: dict[str, dict[str, Any]] = {}
    by_phone: dict[str, dict[str, Any]] = {}
    for contact in contacts:
        email = str(contact.get("email", "")).strip().lower()
        domain = str(contact.get("domain", "")).strip().lower()
        company = str(contact.get("company", "")).strip().lower()
        phone_key = _phone_key(str(contact.get("phone", "")))
        if email:
            by_email[email] = contact
        if domain:
            by_domain.setdefault(domain, contact)
        if company:
            by_company.setdefault(company, contact)
        if phone_key:
            by_phone.setdefault(phone_key, contact)
    return {
        "by_email": by_email,
        "by_domain": by_domain,
        "by_company": by_company,
        "by_phone": by_phone,
    }


def _match_contact(
    subject: str,
    body: str,
    email: str,
    domain: str,
    index: dict[str, Any],
    phone: str = "",
) -> tuple[dict[str, Any] | None, str]:
    phone_key = _phone_key(phone)
    if phone_key:
        contact = index["by_phone"].get(phone_key)
        if contact:
            return contact, "linked_phone"
    contact = index["by_email"].get(email)
    if contact:
        return contact, "linked_email"
    contact = index["by_domain"].get(domain)
    if contact:
        return contact, "linked_domain"
    text = f"{subject} {body}".lower()
    for company, candidate in index["by_company"].items():
        if len(company) >= 3 and company in text:
            return candidate, "linked_company"
    return None, "unlinked"


def normalize_mail(raw: dict[str, Any], source: str = "mailbox") -> dict[str, Any]:
    subject = str(raw.get("subject") or raw.get("type") or "").strip()
    body = str(raw.get("body") or raw.get("body_preview") or "")
    snippet = str(raw.get("snippet") or body[:400]).strip()
    recipient = str(raw.get("to") or raw.get("recipient") or "")
    name, email, domain = _sender(str(raw.get("from") or raw.get("sender") or ""))
    intent = _intent(
        subject,
        f"{snippet} {body}",
        str(raw.get("intent") or "").strip() or infer_intent(f"{subject} {snippet} {body}"),
    )
    uid = str(raw.get("uid") or raw.get("id") or "")
    mail_id = f"{source}:{uid}" if uid else f"{source}:{hashlib.sha1((subject + email).encode()).hexdigest()[:16]}"
    return {
        "id": mail_id,
        "uid": uid,
        "source": source,
        "subject": subject,
        "from": str(raw.get("from") or raw.get("sender") or ""),
        "from_name": name,
        "from_email": email,
        "domain": domain,
        "date": str(raw.get("date") or ""),
        "intent": intent,
        "snippet": snippet[:1000],
        "body": body[:50_000],
        "to": recipient,
        "to_phone": _phone_key(recipient),
        "direction": str(raw.get("direction") or "inbound"),
        "attachments": _infer_attachments(raw),
    }


def _graph(mails: list[dict[str, Any]], missing: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def node(node_id: str, kind: str, label: str, **meta: Any) -> str:
        key = f"{kind}:{node_id}"
        nodes.setdefault(key, {"id": key, "kind": kind, "label": label, **meta})
        return key

    for mail in mails[:500]:
        mail_node = node(mail["id"], "mail", mail["subject"] or "(no subject)", intent=mail["intent"])
        sender_value = mail["from_email"] or mail.get("to") or ""
        if sender_value:
            sender_node = node(sender_value, "sender", mail["from_name"] or sender_value)
            edges.append({"source": mail_node, "target": sender_node, "type": "SENT_BY"})
        if mail["domain"]:
            domain_node = node(mail["domain"], "domain", mail["domain"])
            edges.append({"source": mail_node, "target": domain_node, "type": "FROM_DOMAIN"})
        intent_node = node(mail["intent"], "intent", mail["intent"])
        edges.append({"source": mail_node, "target": intent_node, "type": "HAS_INTENT"})
        for attachment in mail["attachments"]:
            attachment_node = node(
                f"{mail['id']}:{attachment['name']}", "attachment", attachment["name"]
            )
            edges.append(
                {"source": mail_node, "target": attachment_node, "type": "HAS_ATTACHMENT"}
            )
        if mail.get("contact_id"):
            contact_node = node(str(mail["contact_id"]), "contact", mail.get("company") or str(mail["contact_id"]))
            edges.append(
                {"source": mail_node, "target": contact_node, "type": "LINKED_TO_CONTACT"}
            )

    for item in missing[:100]:
        if not (item.get("from_email") or item.get("domain")):
            continue
        missing_node = node(item["from_email"], "missing_link", item["from_email"])
        edges.append(
            {"source": missing_node, "target": node(item.get("domain") or "unknown", "domain", item.get("domain") or "unknown"), "type": "MISSING_IN_CONTACTS"}
        )

    total = len(nodes)
    possible = max(1, total * (total - 1))
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "nodes": total,
            "edges": len(edges),
            "nodes_by_kind": _counts(node["kind"] for node in nodes.values()),
            "edges_by_type": _counts(edge["type"] for edge in edges),
            "density": round(len(edges) / possible, 8),
        },
    }


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value or "unknown"] = counts.get(value or "unknown", 0) + 1
    return dict(sorted(counts.items(), key=lambda item: -item[1]))


def _month(date: str) -> str:
    text = (date or "").strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:31], fmt).strftime("%Y-%m")
        except ValueError:
            continue
    match = re.search(r"(\d{4})-(\d{2})", text)
    return f"{match.group(1)}-{match.group(2)}" if match else "unknown"


def build_insights(
    mails: list[dict[str, Any]],
    contacts: list[dict[str, Any]] | None = None,
    *,
    source: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    index = _contact_index(contacts or [])
    normalized: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for mail in mails:
        item = normalize_mail(mail, source=(source or {}).get("kind", "mailbox") if source else mail.get("source", "mailbox"))
        contact, status = _match_contact(
            item["subject"],
            item["snippet"],
            item["from_email"],
            item["domain"],
            index,
            item.get("to", ""),
        )
        item["link_status"] = status
        item["contact_id"] = int(contact.get("id") or 0) if contact else 0
        item["company"] = str(contact.get("company") or "") if contact else ""
        item["priority"] = "high" if item["intent"] in _HIGH_INTENTS else "normal"
        if contact is None:
            missing.append(
                {
                    "mail_id": item["id"],
                    "subject": item["subject"],
                    "from_email": item["from_email"] or item.get("to", ""),
                    "domain": item["domain"] or item.get("to_phone", ""),
                    "company_hint": _company_hint(item["subject"], item["snippet"]),
                    "reason": "sender not in contacts",
                }
            )
        normalized.append(item)

    normalized.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
    by_intent = _counts(mail["intent"] for mail in normalized)
    by_domain = _counts(mail["domain"] for mail in normalized)
    attachment_count = sum(len(mail["attachments"]) for mail in normalized)
    attachment_purposes = _counts(
        attachment["purpose"] for mail in normalized for attachment in mail["attachments"]
    )
    monthly = _counts(_month(mail["date"]) for mail in normalized)
    linked = sum(1 for mail in normalized if mail["contact_id"])
    total = len(normalized)
    date_coverage = sum(1 for mail in normalized if mail["date"])
    accuracy = 0
    if total:
        accuracy = round(
            100
            * (
                0.5 * (linked / total)
                + 0.3 * (date_coverage / total)
                + 0.2 * (sum(1 for mail in normalized if mail["intent"]) / total)
            )
        )
    forecast_months = {key: value for key, value in monthly.items() if key != "unknown"}
    recent = list(forecast_months.values())[:3]
    next_month = round(sum(recent) / len(recent)) if recent else 0
    return {
        "generated_at": generated_at or _now(),
        "data_available": bool(total),
        "source": source or {},
        "insights": {
            "total": total,
            "linked": linked,
            "unlinked": total - linked,
            "by_intent": by_intent,
            "by_domain": dict(list(by_domain.items())[:20]),
            "attachments": attachment_count,
            "attachment_purposes": attachment_purposes,
            "high_priority": sum(1 for mail in normalized if mail["priority"] == "high"),
            "quotes": by_intent.get("quote_request", 0),
            "orders": by_intent.get("order", 0),
            "complaints": by_intent.get("complaint", 0),
            "monthly_volume": dict(sorted(monthly.items())),
            "forecast_next_month_mails": next_month,
            "accuracy_pct": accuracy,
            "accuracy_reasons": {
                "contact_link_pct": round((linked / total) * 100) if total else 0,
                "date_coverage_pct": round((date_coverage / total) * 100) if total else 0,
                "intent_coverage_pct": 100 if total else 0,
            },
        },
        "mails": normalized,
        "missing_links": {
            "count": len(missing),
            "domains": _counts(item["domain"] or "unknown" for item in missing),
            "samples": missing[:25],
        },
        "graph": _graph(normalized, missing),
    }


def _company_hint(subject: str, body: str) -> str:
    text = f"{subject} - {body}"
    match = re.search(r"\b([A-Z][A-Za-z0-9&.'-]+(?:\s+[A-Z][A-Za-z0-9&.'-]+){0,3})\b", text)
    return match.group(1) if match else ""


def load_insights(path: str | Path | None = None, *, try_gcs: bool = True) -> dict[str, Any]:
    target = snapshot_path(path)
    if target.exists():
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    if try_gcs:
        gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_MAIL)
        blob = f"{settings.GCS_PATH_INSTORE_MAILS}{SNAPSHOT_NAME}"
        raw = gcs.download_blob(blob)
        if raw:
            try:
                payload = json.loads(raw.decode("utf-8"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                return payload
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
    return build_insights([], [], source={"kind": "none"})


def save_insights(payload: dict[str, Any], path: str | Path | None = None, *, upload: bool = True) -> dict[str, Any]:
    target = snapshot_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, default=str)
    target.write_text(text, encoding="utf-8")
    uploaded = False
    if upload:
        gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_MAIL)
        base = settings.GCS_PATH_INSTORE_MAILS
        uploaded = gcs.upload_json(f"{base}{SNAPSHOT_NAME}", payload)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        gcs.upload_json(f"{base}archive/{day}-{SNAPSHOT_NAME}", payload)
    return {"path": str(target), "gcs_uploaded": uploaded}


def load_dump_mails(path: str | Path = "gcs_data/interaction_dump.json") -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [ dict(item, direction="outbound") for item in payload.get("mails", []) ]
