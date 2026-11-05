"""Per-user knowledge graph snapshots and human validation for UAT/DEV."""

from __future__ import annotations

import hashlib
import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..governance.pii import redact_structured
from ..instore_mail import load_insights
from ..knowledge_graph import build_snapshot
from ..llm.router import ModelRouter
from ..models import (
    CompanyVisit,
    Contact,
    ErpDispatch,
    ErpOrder,
    MarketingCompany,
    MessageTemplate,
    TallySale,
    User,
)
from ..security import get_current_user, is_admin_user
from ..services import GCSStorage

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph", "review"])


class ReviewDecisionIn(BaseModel):
    action: Literal["accept", "reject"]
    note: str = Field(default="", max_length=2000)


class GraphChatIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    selected_node: str = Field(default="", max_length=255)


class GraphFeedbackIn(BaseModel):
    graph_version: str = Field(default="", max_length=64)
    question: str = Field(..., min_length=2, max_length=2000)
    answer: str = Field(default="", max_length=4000)
    correction: str = Field(default="", max_length=2000)
    rating: int = Field(default=3, ge=1, le=5)


class GraphFeedbackDecisionIn(BaseModel):
    action: Literal["accept", "reject"]
    note: str = Field(default="", max_length=1000)


def _environment() -> str:
    return (settings.DEPLOY_ENV or settings.ENV or "development").lower()


def _ensure_review_environment() -> None:
    environment = _environment()
    allowed = {"dev", "development", "preprod", "stage", "staging", "uat", "test"}
    if settings.ENV.lower() in {"prod", "production"} or environment not in allowed:
        raise HTTPException(status_code=404, detail="Graph review is available only in DEV/UAT environments")
    if environment in {"stage", "staging", "uat"}:
        try:
            active_until = datetime.fromisoformat(settings.UAT_ENABLED_UNTIL).date()
        except ValueError:
            active_until = None
        if not settings.UAT_ENABLED or active_until is None or active_until < datetime.now(timezone.utc).date():
            raise HTTPException(status_code=404, detail="UAT graph review window is closed")


def _blob_path(user_id: int, filename: str = "current.json") -> str:
    prefix = settings.KNOWLEDGE_GRAPH_GCS_PREFIX.strip("/")
    if not prefix or ".." in prefix.split("/"):
        raise HTTPException(status_code=500, detail="Knowledge graph storage prefix is invalid")
    return f"{prefix}/users/{user_id}/{filename}"


def _local_path(user_id: int, filename: str = "current.json") -> Path:
    return Path(tempfile.gettempdir()) / "ai_pitch_agent" / "knowledge_graph" / f"user_{user_id}" / filename


def _store_user_json(user_id: int, filename: str, payload: dict[str, Any]) -> dict[str, Any]:
    gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_CONTACTS)
    blob_path = _blob_path(user_id, filename)
    path = _local_path(user_id, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)

    uploaded = gcs.upload_json(blob_path, payload) if gcs.available else False
    return {
        "stored": "gcs+local" if uploaded else "local-cache",
        "gcs_uploaded": bool(uploaded),
        "path": blob_path if uploaded else "",
    }


def _store_graph(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_CONTACTS)
    blob_path = _blob_path(user_id)
    payload["storage"] = "gcs+local" if gcs.available else "local-cache"
    path = _local_path(user_id, "current.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)
    uploaded = gcs.upload_json(blob_path, payload) if gcs.available else False
    if gcs.available and not uploaded:
        payload["storage"] = "local-cache"
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temporary.replace(path)
    return {"stored": "gcs+local" if uploaded else "local-cache", "gcs_uploaded": bool(uploaded), "path": blob_path if uploaded else ""}


def _load_user_json(user_id: int, filename: str, default: Any) -> Any:
    gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_CONTACTS)
    if gcs.available:
        raw = gcs.download_blob(_blob_path(user_id, filename))
        if raw:
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
    path = _local_path(user_id, filename)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return default


def _load_graph(user_id: int) -> dict[str, Any]:
    return _load_user_json(user_id, "current.json", {
        "schema_version": 1,
        "environment": _environment(),
        "version": "",
        "generated_at": "",
        "nodes": [],
        "edges": [],
        "stats": {"nodes": 0, "edges": 0, "pending_edges": 0, "nodes_by_kind": {}, "edges_by_relation": {}, "sources": {}},
    })


def _feedback_items(user_id: int) -> list[dict[str, Any]]:
    return _load_user_json(user_id, "feedback.json", [])


def _user_sources(user: User, db: Session) -> tuple[list[dict], ...]:
    contacts = [
        {
            "id": row.id,
            "name": row.name,
            "company": row.company,
            "domain": row.domain,
            "intent": row.intent,
            "source": row.source,
        }
        for row in db.query(Contact).filter(Contact.user_id == user.id).order_by(Contact.id.desc()).limit(5000).all()
    ]
    marketing = [
        {
            "id": row.id,
            "company": row.company,
            "category": row.category,
            "funnel_stage": row.funnel_stage,
            "sales_progress": row.sales_progress,
            "requirements": row.requirements,
            "next_action": row.next_action,
            "follow_up_date": row.follow_up_date,
        }
        for row in db.query(MarketingCompany).filter(MarketingCompany.user_id == user.id).order_by(MarketingCompany.id.desc()).limit(5000).all()
    ]
    visits = [
        {
            "id": row.id,
            "company": row.company,
            "visit_date": row.visit_date,
            "outcome": row.outcome,
            "next_action": row.next_action,
            "follow_up_date": row.follow_up_date,
        }
        for row in db.query(CompanyVisit).filter(CompanyVisit.user_id == user.id).order_by(CompanyVisit.id.desc()).limit(2000).all()
    ]
    contact_ids = {row["id"] for row in contacts}
    try:
        snapshot = load_insights()
        mails = [
            mail for mail in snapshot.get("mails", [])[:5000]
            if int(mail.get("contact_id") or 0) in contact_ids
        ]
    except Exception:  # noqa: BLE001 - optional mail source must not block graph refresh
        mails = []
    orders = [
        {"order_no": row.order_no, "customer": row.customer, "order_date": row.order_date,
         "report_date": row.report_date, "status": row.status, "total_value": row.total_value}
        for row in db.query(ErpOrder).order_by(ErpOrder.id.desc()).limit(1000).all()
    ]
    dispatches = [
        {"dispatch_no": row.dispatch_no, "customer": row.customer, "plant": row.plant,
         "report_date": row.report_date, "status": row.status,
         "schedule_qty": row.schedule_qty, "dispatched_qty": row.dispatched_qty}
        for row in db.query(ErpDispatch).order_by(ErpDispatch.id.desc()).limit(1000).all()
    ]
    tally_sales = [
        {"source_file": row.source_file, "source_row": row.source_row, "sale_date": row.sale_date,
         "period": row.period, "buyer": row.buyer, "voucher_no": row.voucher_no,
         "item_name": row.item_name, "quantity": row.quantity, "value": row.value}
        for row in db.query(TallySale).order_by(TallySale.id.desc()).limit(5000).all()
    ]
    templates = [
        {"id": row.id, "name": row.name, "channel": row.channel, "strategy": row.strategy,
         "funnel_stage": row.funnel_stage, "variables": row.variables, "is_active": row.is_active}
        for row in db.query(MessageTemplate).filter(
            MessageTemplate.user_id.in_([0, user.id]), MessageTemplate.is_active.is_(True)
        ).order_by(MessageTemplate.id.asc()).limit(250).all()
    ]
    return contacts, marketing, visits, mails, orders, dispatches, tally_sales, templates


@router.get("/summary")
def graph_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_review_environment()
    graph = _load_graph(user.id)
    return {
        "environment": _environment(),
        "review_enabled": True,
        "generated_at": graph.get("generated_at", ""),
        "version": graph.get("version", ""),
        "storage": graph.get("storage", "not-built"),
        "stats": graph.get("stats") or {},
        "pending_reviews": graph.get("stats", {}).get("pending_edges", 0),
        "chat_enabled": bool(settings.KNOWLEDGE_GRAPH_CHAT_ENABLED and settings.LLM_ENABLED),
    }


@router.get("")
def read_graph(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_review_environment()
    return _load_graph(user.id)


@router.post("/build")
def build_user_graph(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_review_environment()
    contacts, marketing, visits, mails, orders, dispatches, tally_sales, templates = _user_sources(user, db)
    graph = build_snapshot(
        contacts=contacts,
        marketing_companies=marketing,
        visits=visits,
        mails=mails,
        orders=orders,
        dispatches=dispatches,
        tally_sales=tally_sales,
        templates=templates,
        environment=_environment(),
    )
    serialized = json.dumps(
        {"nodes": graph["nodes"], "edges": graph["edges"]},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    version = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20]
    now = datetime.now(timezone.utc).isoformat()
    graph["version"] = version
    graph["generated_at"] = now

    previous_reviews = {
        edge.get("edge_key"): edge
        for edge in _load_graph(user.id).get("edges", [])
        if edge.get("needs_review") and edge.get("edge_key")
    }
    candidates = [edge for edge in graph["edges"] if edge.get("needs_review")]
    for edge in candidates:
        old = previous_reviews.get(edge["edge_key"])
        if old and old.get("review_status") in {"accepted", "rejected"}:
            edge["review_status"] = old["review_status"]
            edge["review_note"] = old.get("review_note", "")
            edge["reviewed_by"] = old.get("reviewed_by", "")
            edge["reviewed_at"] = old.get("reviewed_at", "")
        else:
            edge["review_status"] = "pending"
        edge["graph_owner_id"] = user.id
    graph["stats"]["pending_edges"] = sum(edge.get("review_status") == "pending" for edge in graph["edges"])
    storage = _store_graph(user.id, graph)
    log_event(
        db,
        action="knowledge_graph.build",
        actor_user_id=user.id,
        resource_type="knowledge_graph",
        resource_id=version,
        tenant_id=user.domain,
        detail={"nodes": graph["stats"]["nodes"], "edges": graph["stats"]["edges"], "pending": graph["stats"]["pending_edges"]},
    )
    db.commit()
    return {"ok": True, "version": version, "storage": storage, "stats": graph["stats"], "generated_at": now}


@router.get("/reviews")
def list_graph_reviews(
    status: Literal["pending", "accepted", "rejected"] | None = None,
    team: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
):
    _ensure_review_environment()
    graph_sources: list[tuple[int, dict[str, Any]]] = [(user.id, _load_graph(user.id))]
    if team:
        if not is_admin_user(user):
            raise HTTPException(status_code=403, detail="Admin access required for team review queue")
        gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_CONTACTS)
        if gcs.available:
            prefix = f"{settings.KNOWLEDGE_GRAPH_GCS_PREFIX.strip('/')}/users/"
            blobs = gcs.list_blobs(prefix=prefix, suffixes=(".json",))
            owner_ids = set()
            for blob in blobs:
                name = str(blob.get("name", ""))
                if not name.endswith("/current.json"):
                    continue
                remainder = name[len(prefix):]
                owner_text = remainder.split("/", 1)[0]
                if owner_text.isdigit():
                    owner_ids.add(int(owner_text))
            for owner_id in sorted(owner_ids)[:100]:
                if owner_id != user.id:
                    graph_sources.append((owner_id, _load_graph(owner_id)))
    items = []
    for owner_id, graph in graph_sources:
        labels = {node.get("id"): node.get("label", node.get("id")) for node in graph.get("nodes", [])}
        for edge in graph.get("edges", []):
            if not edge.get("needs_review"):
                continue
            edge_status = edge.get("review_status", "pending")
            if status and edge_status != status:
                continue
            items.append(
                {
                    "id": edge.get("edge_key"),
                    "edge_key": edge.get("edge_key"),
                    "graph_owner_id": owner_id,
                    "graph_version": graph.get("version", ""),
                    "source": labels.get(edge.get("source"), edge.get("source")),
                    "target": labels.get(edge.get("target"), edge.get("target")),
                    "relation": edge.get("relation", ""),
                    "confidence": round(float(edge.get("confidence", 0)), 3),
                    "evidence": edge.get("evidence", ""),
                    "status": edge_status,
                    "review_note": edge.get("review_note", ""),
                    "reviewer": edge.get("reviewed_by", ""),
                    "reviewed_at": edge.get("reviewed_at", ""),
                }
            )
    items.sort(key=lambda item: (item["status"] != "pending", item["graph_owner_id"], item["relation"], item["edge_key"]))
    items = items[:limit]
    return {
        "items": items,
        "pending": sum(item["status"] == "pending" for item in items),
        "team": bool(team),
    }


@router.post("/reviews/{review_id}")
def decide_graph_review(
    review_id: str,
    payload: ReviewDecisionIn,
    graph_owner_id: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_review_environment()
    owner_id = graph_owner_id or user.id
    if owner_id != user.id and not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin access required for team review")
    graph = _load_graph(owner_id)
    edge = next((item for item in graph.get("edges", []) if item.get("edge_key") == review_id), None)
    if edge is None or not edge.get("needs_review"):
        raise HTTPException(status_code=404, detail="Graph review not found")
    if edge.get("review_status") != "pending":
        raise HTTPException(status_code=409, detail=f"Relationship already reviewed as {edge.get('review_status')}")
    edge["review_status"] = "accepted" if payload.action == "accept" else "rejected"
    edge["review_note"] = payload.note.strip()
    edge["reviewed_by"] = user.email
    edge["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    graph.setdefault("stats", {})["pending_edges"] = sum(
        item.get("needs_review") and item.get("review_status") == "pending"
        for item in graph.get("edges", [])
    )
    storage = _store_graph(owner_id, graph)
    log_event(
        db,
        action=f"knowledge_graph.{payload.action}",
        actor_user_id=user.id,
        resource_type="graph_edge",
        resource_id=review_id,
        tenant_id=user.domain,
        detail={"relation": edge.get("relation"), "graph_version": graph.get("version"), "note_present": bool(payload.note.strip()), "storage": storage["stored"]},
    )
    db.commit()
    return {"id": review_id, "status": edge["review_status"], "reviewed_at": edge["reviewed_at"], "storage": storage["stored"]}


def _graph_context(graph: dict[str, Any], selected_node: str = "") -> str:
    nodes = graph.get("nodes", [])
    node_labels = {node["id"]: node.get("label", node["kind"]) for node in nodes}
    if selected_node:
        nodes = [node for node in nodes if node.get("id") == selected_node]
    selected_ids = {node.get("id") for node in nodes}
    edges = [
        edge for edge in graph.get("edges", [])
        if edge.get("review_status") == "accepted"
        and (not selected_ids or edge.get("source") in selected_ids or edge.get("target") in selected_ids)
    ][:40]
    lines = [
        f"Environment: {graph.get('environment', 'unknown')}; graph version: {graph.get('version', 'none')}",
        f"Nodes: {len(graph.get('nodes', []))}; accepted relationships in context: {len(edges)}; pending review: {graph.get('stats', {}).get('pending_edges', 0)}",
        "Relevant nodes:",
    ]
    lines.extend(f"- {node.get('kind')}: {node.get('label')}" for node in nodes[:40])
    lines.append("Relationships:")
    lines.extend(
        f"- {node_labels.get(edge.get('source'), edge.get('source'))} --{edge.get('relation')}--> "
        f"{node_labels.get(edge.get('target'), edge.get('target'))} [{edge.get('review_status')}]"
        for edge in edges
    )
    return "\n".join(lines)[:10000]


def _reviewed_feedback_examples(user_id: int, limit: int = 3) -> list[dict[str, str]]:
    examples = []
    for item in reversed(_feedback_items(user_id)):
        if item.get("status") != "accepted_sample":
            continue
        correction = item.get("correction") or item.get("answer") or ""
        if not correction:
            continue
        examples.append(
            {
                "question": str(item.get("question") or "")[:400],
                "human_answer": str(correction)[:800],
            }
        )
        if len(examples) >= limit:
            break
    return examples


@router.post("/chat")
def graph_chat(
    payload: GraphChatIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_review_environment()
    graph = _load_graph(user.id)
    if not graph.get("version"):
        raise HTTPException(status_code=409, detail="Build a graph snapshot after syncing source data first")
    context = _graph_context(graph, payload.selected_node)
    reviewed_examples = _reviewed_feedback_examples(user.id)
    examples_context = "\n".join(
        f"- Question: {item['question']}\n  Human-validated answer: {item['human_answer']}"
        for item in reviewed_examples
    ) or "No human-reviewed examples are available."
    prompt = (
        "Answer using only this graph snapshot and its human-accepted relationships. "
        "Do not infer facts from pending or rejected edges. If no accepted relationship answers the question, say so.\n\n"
        f"GRAPH SNAPSHOT\n{context}\n\nHUMAN-REVIEWED EXAMPLES (style guidance only)\n{examples_context}\n\nQUESTION\n{payload.question}"
    )
    from ..llm.guardrails import scan_prompt

    report = scan_prompt(prompt, max_chars=settings.LLM_MAX_INPUT_CHARS, redact_pii=True)
    if not report.allowed:
        raise HTTPException(status_code=400, detail="Chat prompt blocked by guardrails")

    if settings.KNOWLEDGE_GRAPH_CHAT_ENABLED and settings.LLM_ENABLED:
        try:
            result = ModelRouter().run(
                "knowledge_graph_chat",
                report.sanitized,
                system="You are a careful sales-data reviewer. Do not invent relationships.",
                user_id=user.id,
                db=db,
                temperature=0.1,
                redact_pii=True,
            )
            if not result.output_report.allowed:
                raise HTTPException(status_code=502, detail="Chat output failed validation")
            reply = result.result.text
            provider = result.result.provider
            model = result.result.model
            cost = result.cost_micros
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001 - use the free offline summary fallback
            reply = _fallback_graph_answer(graph, payload.question, payload.selected_node)
            provider, model, cost = "rules", "offline-summary", 0
    else:
        reply = _fallback_graph_answer(graph, payload.question, payload.selected_node)
        provider, model, cost = "rules", "offline-summary", 0

    log_event(
        db,
        action="knowledge_graph.chat",
        actor_user_id=user.id,
        resource_type="knowledge_graph",
        resource_id=graph["version"],
        tenant_id=user.domain,
        detail={"provider": provider, "model": model, "question_length": len(payload.question)},
    )
    db.commit()
    return {
        "reply": reply,
        "provider": provider,
        "model": model,
        "cost_micros": cost,
        "graph_version": graph["version"],
        "pending_edges": graph.get("stats", {}).get("pending_edges", 0),
    }


def _fallback_graph_answer(graph: dict[str, Any], question: str, selected_node: str = "") -> str:
    nodes = graph.get("nodes", [])
    lookup = {node["id"]: node for node in nodes}
    query_tokens = {word for word in question.lower().split() if len(word) > 2}
    matches = [
        node for node in nodes
        if (selected_node and node.get("id") == selected_node)
        or any(word in str(node.get("label", "")).lower() for word in query_tokens)
    ][:8]
    selected_ids = {node.get("id") for node in matches}
    edges = [
        edge for edge in graph.get("edges", [])
        if edge.get("review_status") == "accepted"
        and (edge.get("source") in selected_ids or edge.get("target") in selected_ids)
    ][:12]
    lines = [
        f"This {graph.get('environment', 'development')} snapshot contains "
        f"{graph.get('stats', {}).get('nodes', 0)} nodes and {graph.get('stats', {}).get('edges', 0)} relationships."
    ]
    if matches:
        lines.append("Matching records: " + "; ".join(f"{node.get('kind')}: {node.get('label')}" for node in matches))
    if edges:
        lines.append("Related edges: " + "; ".join(
            f"{lookup.get(edge['source'], {}).get('label', edge['source'])} {edge['relation']} "
            f"{lookup.get(edge['target'], {}).get('label', edge['target'])} ({edge.get('review_status')})"
            for edge in edges
        ))
    pending = graph.get("stats", {}).get("pending_edges", 0)
    lines.append(f"{pending} relationship(s) still need human validation. Pending links are suggestions, not confirmed facts.")
    return "\n".join(lines)


@router.post("/feedback", status_code=201)
def graph_feedback(
    payload: GraphFeedbackIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_review_environment()
    items = _feedback_items(user.id)
    row = {
        "id": uuid.uuid4().hex[:16],
        "user_id": user.id,
        "graph_version": payload.graph_version,
        "question": redact_structured(payload.question),
        "answer": redact_structured(payload.answer),
        "correction": redact_structured(payload.correction),
        "rating": payload.rating,
        "status": "pending_evaluation",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    items.append(row)
    items = items[-200:]
    storage = _store_user_json(user.id, "feedback.json", items)
    log_event(
        db,
        action="knowledge_graph.feedback",
        actor_user_id=user.id,
        resource_type="knowledge_graph",
        resource_id=payload.graph_version,
        tenant_id=user.domain,
        detail={"rating": payload.rating, "correction_provided": bool(payload.correction.strip()), "storage": storage["stored"]},
    )
    db.commit()
    return {"id": row["id"], "status": row["status"], "rating": row["rating"], "storage": storage["stored"]}


@router.get("/feedback")
def list_graph_feedback(
    team: bool = False,
    user: User = Depends(get_current_user),
):
    _ensure_review_environment()
    if not team:
        return list(reversed(_feedback_items(user.id)[-25:]))
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin access required for team feedback")
    gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_CONTACTS)
    if not gcs.available:
        return list(reversed(_feedback_items(user.id)[-25:]))
    prefix = f"{settings.KNOWLEDGE_GRAPH_GCS_PREFIX.strip('/')}/users/"
    items = []
    for blob in gcs.list_blobs(prefix=prefix, suffixes=("feedback.json",))[:100]:
        name = str(blob.get("name", ""))
        remainder = name[len(prefix):]
        owner = remainder.split("/", 1)[0]
        if not owner.isdigit():
            continue
        for item in _load_user_json(int(owner), "feedback.json", [])[-25:]:
            items.append({**item, "graph_owner_id": int(owner)})
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return items[:200]


@router.post("/feedback/{feedback_id}/review")
def review_graph_feedback(
    feedback_id: str,
    payload: GraphFeedbackDecisionIn,
    graph_owner_id: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
):
    _ensure_review_environment()
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin access required to validate feedback samples")
    owner_id = graph_owner_id or user.id
    items = _feedback_items(owner_id)
    item = next((entry for entry in items if entry.get("id") == feedback_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Feedback sample not found")
    if item.get("status") != "pending_evaluation":
        raise HTTPException(status_code=409, detail="Feedback sample has already been reviewed")
    item["status"] = "accepted_sample" if payload.action == "accept" else "rejected_sample"
    item["reviewed_by"] = user.email
    item["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    item["review_note"] = redact_structured(payload.note)
    storage = _store_user_json(owner_id, "feedback.json", items[-200:])
    return {"id": feedback_id, "status": item["status"], "storage": storage["stored"]}
