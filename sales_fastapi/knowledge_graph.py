"""Deterministic, tenant-scoped graph construction from normalized sales records."""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()


def _key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def _company_id(name: str) -> str:
    return f"company:{_key(_normal(name))}"


def _edge(source: str, target: str, relation: str, *, confidence: float = 1.0,
          evidence: str = "", needs_review: bool = False) -> dict[str, Any]:
    edge_key = _key(f"{source}|{relation}|{target}")
    return {
        "id": edge_key,
        "edge_key": edge_key,
        "source": source,
        "target": target,
        "relation": relation,
        "confidence": round(max(0.0, min(float(confidence), 1.0)), 3),
        "evidence": evidence[:500],
        "review_status": "pending" if needs_review else "accepted",
        "needs_review": needs_review,
    }


def build_snapshot(
    *,
    contacts: list[dict[str, Any]],
    marketing_companies: list[dict[str, Any]],
    visits: list[dict[str, Any]],
    mails: list[dict[str, Any]],
    orders: list[dict[str, Any]] | None = None,
    dispatches: list[dict[str, Any]] | None = None,
    tally_sales: list[dict[str, Any]] | None = None,
    templates: list[dict[str, Any]] | None = None,
    environment: str,
) -> dict[str, Any]:
    """Build graph JSON; only ambiguous cross-source matches require review."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    def add_company(name: str, source: str, **attributes: Any) -> str:
        name = _text(name)
        if not name:
            return ""
        node_id = _company_id(name)
        node = nodes.setdefault(
            node_id,
            {"id": node_id, "kind": "company", "label": name, "sources": []},
        )
        if source not in node["sources"]:
            node["sources"].append(source)
        for field, value in attributes.items():
            if value and not node.get(field):
                node[field] = value
        return node_id

    for contact in contacts:
        contact_id = int(contact.get("id") or 0)
        if not contact_id:
            continue
        node_id = f"contact:{contact_id}"
        company = _text(contact.get("company"))
        nodes[node_id] = {
            "id": node_id,
            "kind": "contact",
            "label": _text(contact.get("name")) or company or "Contact",
            "company": company,
            "domain": _text(contact.get("domain")),
            "intent": _text(contact.get("intent")) or "general",
            "source": _text(contact.get("source")) or "contact",
        }
        company_id = add_company(company, "contacts")
        if company_id:
            edge = _edge(node_id, company_id, "CONTACT_AT_COMPANY")
            edges[edge["id"]] = edge
        intent = _text(contact.get("intent")) or "general"
        intent_id = f"intent:{_key(intent)}"
        nodes.setdefault(intent_id, {"id": intent_id, "kind": "intent", "label": intent})
        edge = _edge(node_id, intent_id, "CONTACT_HAS_INTENT")
        edges[edge["id"]] = edge

    for company in marketing_companies:
        company_name = _text(company.get("company"))
        company_id = add_company(
            company_name,
            "marketing_companies",
            category=_text(company.get("category")),
            funnel_stage=_text(company.get("funnel_stage")) or "awareness",
            sales_progress=_text(company.get("sales_progress")) or "new",
            requirements=_text(company.get("requirements"))[:1000],
            next_action=_text(company.get("next_action"))[:500],
            follow_up_date=_text(company.get("follow_up_date")),
        )
        if company_id:
            stage = _text(company.get("funnel_stage")) or "awareness"
            stage_id = f"funnel_stage:{stage}"
            nodes.setdefault(stage_id, {"id": stage_id, "kind": "funnel_stage", "label": stage})
            edge = _edge(company_id, stage_id, "COMPANY_IN_FUNNEL_STAGE")
            edges[edge["id"]] = edge

    # Candidate cross-list matches are bounded and deterministic; humans approve them.
    contacts_by_token: dict[str, list[dict[str, Any]]] = {}
    for contact in contacts:
        words = {word for word in _normal(contact.get("company")).split() if len(word) > 3}
        for word in words:
            contacts_by_token.setdefault(word, []).append(contact)
    candidate_count = 0
    for company in marketing_companies:
        marketing_name = _text(company.get("company"))
        marketing_norm = _normal(marketing_name)
        if not marketing_norm:
            continue
        words = {word for word in marketing_norm.split() if len(word) > 3}
        candidates: dict[int, dict[str, Any]] = {}
        for word in words:
            for contact in contacts_by_token.get(word, [])[:25]:
                candidates[int(contact.get("id") or 0)] = contact
        for contact in candidates.values():
            contact_id = int(contact.get("id") or 0)
            contact_norm = _normal(contact.get("company"))
            if not contact_id or not contact_norm or contact_norm == marketing_norm:
                continue
            confidence = SequenceMatcher(None, contact_norm, marketing_norm).ratio()
            if confidence < 0.78:
                continue
            source = f"contact:{contact_id}"
            target = _company_id(marketing_name)
            edge = _edge(
                source,
                target,
                "POSSIBLE_COMPANY_MATCH",
                confidence=confidence,
                evidence=f"Contact company '{_text(contact.get('company'))}' resembles marketing company '{marketing_name}'.",
                needs_review=True,
            )
            edges[edge["id"]] = edge
            candidate_count += 1
            if candidate_count >= 500:
                break
        if candidate_count >= 500:
            break

    for visit in visits:
        visit_id = int(visit.get("id") or 0)
        company = _text(visit.get("company"))
        company_id = add_company(company, "company_visits")
        if not visit_id or not company_id:
            continue
        node_id = f"visit:{visit_id}"
        nodes[node_id] = {
            "id": node_id,
            "kind": "visit",
            "label": f"Visit · {_text(visit.get('visit_date')) or 'date unknown'}",
            "visit_date": _text(visit.get("visit_date")),
            "outcome": _text(visit.get("outcome")),
            "next_action": _text(visit.get("next_action"))[:500],
            "follow_up_date": _text(visit.get("follow_up_date")),
        }
        edge = _edge(node_id, company_id, "VISIT_FOR_COMPANY")
        edges[edge["id"]] = edge

    orders = orders or []
    for order in orders:
        order_number = _text(order.get("order_no"))
        if not order_number:
            continue
        order_key = f"{_text(order.get('report_date'))}|{order_number}"
        node_id = f"order:{_key(order_key)}"
        company = _text(order.get("customer"))
        nodes[node_id] = {
            "id": node_id,
            "kind": "erp_order",
            "label": order_number,
            "company": company,
            "status": _text(order.get("status")),
            "date": _text(order.get("order_date") or order.get("report_date")),
            "value": float(order.get("total_value") or 0),
        }
        company_id = add_company(company, "erp_orders")
        if company_id:
            edge = _edge(node_id, company_id, "ORDER_FOR_COMPANY")
            edges[edge["id"]] = edge

    dispatches = dispatches or []
    for dispatch in dispatches:
        dispatch_number = _text(dispatch.get("dispatch_no"))
        if not dispatch_number:
            continue
        dispatch_key = f"{_text(dispatch.get('report_date'))}|{dispatch_number}"
        node_id = f"dispatch:{_key(dispatch_key)}"
        company = _text(dispatch.get("customer"))
        nodes[node_id] = {
            "id": node_id,
            "kind": "erp_dispatch",
            "label": dispatch_number,
            "company": company,
            "plant": _text(dispatch.get("plant")),
            "status": _text(dispatch.get("status")),
            "date": _text(dispatch.get("report_date")),
            "scheduled_qty": float(dispatch.get("schedule_qty") or 0),
            "dispatched_qty": float(dispatch.get("dispatched_qty") or 0),
        }
        company_id = add_company(company, "erp_dispatch")
        if company_id:
            edge = _edge(node_id, company_id, "DISPATCH_FOR_COMPANY")
            edges[edge["id"]] = edge

    tally_sales = tally_sales or []
    for sale in tally_sales:
        source_row = _text(sale.get("source_row"))
        source_file = _text(sale.get("source_file"))
        if not source_file and not source_row:
            continue
        node_id = f"tally_sale:{_key(f'{source_file}|{source_row}')}"
        buyer = _text(sale.get("buyer"))
        item = _text(sale.get("item_name"))
        nodes[node_id] = {
            "id": node_id,
            "kind": "tally_sale",
            "label": _text(sale.get("voucher_no")) or f"Sale row {source_row}",
            "date": _text(sale.get("sale_date")),
            "period": _text(sale.get("period")),
            "item": item,
            "quantity": float(sale.get("quantity") or 0),
            "value": float(sale.get("value") or 0),
            "source": source_file,
        }
        company_id = add_company(buyer, "tally_sales")
        if company_id:
            edge = _edge(node_id, company_id, "SALE_TO_COMPANY")
            edges[edge["id"]] = edge
        if item:
            product_id = f"product:{_key(_normal(item))}"
            nodes.setdefault(product_id, {"id": product_id, "kind": "product", "label": item})
            edge = _edge(node_id, product_id, "SALE_OF_PRODUCT")
            edges[edge["id"]] = edge

    templates = templates or []
    for template in templates:
        template_id = int(template.get("id") or 0)
        if not template_id:
            continue
        node_id = f"template:{template_id}"
        stage = _text(template.get("funnel_stage")) or "awareness"
        nodes[node_id] = {
            "id": node_id,
            "kind": "message_template",
            "label": _text(template.get("name")) or f"Template {template_id}",
            "channel": _text(template.get("channel")),
            "strategy": _text(template.get("strategy")),
            "funnel_stage": stage,
            "variables": [str(item)[:64] for item in (template.get("variables") or [])[:20]],
            "active": bool(template.get("is_active", True)),
            "source": "message_templates",
        }
        stage_id = f"funnel_stage:{stage}"
        nodes.setdefault(stage_id, {"id": stage_id, "kind": "funnel_stage", "label": stage})
        edge = _edge(node_id, stage_id, "TEMPLATE_TARGETS_STAGE")
        edges[edge["id"]] = edge

    contact_ids = {int(contact.get("id") or 0) for contact in contacts}
    for mail in mails:
        contact_id = int(mail.get("contact_id") or 0)
        if not contact_id or contact_id not in contact_ids:
            continue
        mail_key = _text(mail.get("uid") or mail.get("id") or mail.get("subject"))
        if not mail_key:
            continue
        node_id = f"mail:{_key(mail_key)}"
        nodes[node_id] = {
            "id": node_id,
            "kind": "mail",
            "label": _text(mail.get("working_title") or mail.get("subject")) or "Mail",
            "date": _text(mail.get("date"))[:40],
            "intent": _text(mail.get("intent")),
            "outcome": _text(mail.get("outcome")),
            "source": _text(mail.get("source")) or "instore_snapshot",
        }
        match_method = _text(mail.get("match_method"))
        confidence = 0.99 if match_method in {"linked_email", "linked_phone"} else 0.82
        edge = _edge(
            node_id,
            f"contact:{contact_id}",
            "MAIL_LINKED_TO_CONTACT",
            confidence=confidence,
            evidence=f"Mail/contact link method: {match_method or 'snapshot link'}.",
            needs_review=confidence < 0.95,
        )
        edges[edge["id"]] = edge

    edge_items = sorted(edges.values(), key=lambda item: (item["review_status"] != "pending", item["relation"], item["id"]))
    node_items = sorted(nodes.values(), key=lambda item: (item["kind"], item["label"].casefold(), item["id"]))
    kind_counts: dict[str, int] = {}
    for node in node_items:
        kind_counts[node["kind"]] = kind_counts.get(node["kind"], 0) + 1
    relation_counts: dict[str, int] = {}
    for edge in edge_items:
        relation_counts[edge["relation"]] = relation_counts.get(edge["relation"], 0) + 1
    return {
        "schema_version": 1,
        "environment": environment,
        "nodes": node_items,
        "edges": edge_items,
        "stats": {
            "nodes": len(node_items),
            "edges": len(edge_items),
            "pending_edges": sum(edge["review_status"] == "pending" for edge in edge_items),
            "nodes_by_kind": kind_counts,
            "edges_by_relation": relation_counts,
            "sources": {
                "contacts": len(contacts),
                "marketing_companies": len(marketing_companies),
                "company_visits": len(visits),
                "linked_mails": len([mail for mail in mails if int(mail.get("contact_id") or 0) in contact_ids]),
                "erp_orders": len(orders),
                "erp_dispatches": len(dispatches),
                "tally_sales": len(tally_sales),
                "templates": len(templates),
            },
        },
    }
