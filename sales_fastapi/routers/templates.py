"""Message template management (email / WhatsApp / LinkedIn / WeChat)."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..governance.audit import log_event
from ..models import MessageTemplate, User
from ..outreach_templates import (
    CHANNELS,
    DEFAULT_TEMPLATES,
    FUNNEL_STAGES,
    SENDER,
    STRATEGIES,
)
from ..schemas import TemplateCreate, TemplateOut, TemplateUpdate
from ..security import get_current_user
from ..services import GCSStorage
from ..templating import variables_used

router = APIRouter(prefix="/templates", tags=["templates"])

GCS_BUCKET = "kalika_enterprises"
GCS_PATH = "Mail_templates/"


@router.get("/meta")
def templates_meta(user: User = Depends(get_current_user)):
    return {
        "channels": CHANNELS,
        "strategies": STRATEGIES,
        "funnel_stages": FUNNEL_STAGES,
        "sender": SENDER,
    }


def _template_out(row: MessageTemplate) -> dict[str, Any]:
    """Serialize a template defensively so legacy rows never break the list."""
    variables = row.variables
    if isinstance(variables, str):
        variables = [v.strip() for v in variables.split(",") if v.strip()]
    if not isinstance(variables, (list, tuple)):
        variables = []
    return {
        "id": row.id,
        "name": row.name or "Untitled",
        "channel": row.channel or "email",
        "strategy": row.strategy or "cold_outreach",
        "funnel_stage": row.funnel_stage or "awareness",
        "subject": row.subject or "",
        "body": row.body or "",
        "variables": [str(v) for v in variables],
        "is_active": bool(row.is_active),
        "created_at": str(row.created_at),
        "updated_at": str(row.updated_at),
    }


@router.get("")
def list_templates(
    channel: str | None = Query(default=None),
    strategy: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(MessageTemplate).filter(
        MessageTemplate.user_id.in_([user.id, 0]), MessageTemplate.is_active.is_(True)
    )
    if channel:
        query = query.filter(MessageTemplate.channel == channel)
    if strategy:
        query = query.filter(MessageTemplate.strategy == strategy)
    rows = query.order_by(MessageTemplate.updated_at.desc()).all()
    return [_template_out(row) for row in rows]


@router.post("", response_model=TemplateOut, status_code=201)
def create_template(
    payload: TemplateCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    variables = payload.variables or variables_used(payload.subject + " " + payload.body)
    template = MessageTemplate(
        user_id=user.id, **payload.model_dump(exclude={"variables"}), variables=variables
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    log_event(
        db,
        action="template.create",
        actor_user_id=user.id,
        resource_type="template",
        resource_id=str(template.id),
        tenant_id=user.domain,
        detail={"channel": template.channel},
        commit=True,
    )
    return template


@router.patch("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: int,
    payload: TemplateUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = (
        db.query(MessageTemplate)
        .filter(MessageTemplate.id == template_id, MessageTemplate.user_id == user.id)
        .first()
    )
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    changed = payload.model_dump(exclude_unset=True)
    for field, value in changed.items():
        setattr(template, field, value)
    if "subject" in changed or "body" in changed:
        template.variables = variables_used(template.subject + " " + template.body)
    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = (
        db.query(MessageTemplate)
        .filter(MessageTemplate.id == template_id, MessageTemplate.user_id == user.id)
        .first()
    )
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template)
    db.commit()


@router.post("/seed")
def seed_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = {
        (row.name, row.channel)
        for row in db.query(MessageTemplate.name, MessageTemplate.channel)
        .filter(MessageTemplate.user_id == user.id)
        .all()
    }
    created = 0
    for item in DEFAULT_TEMPLATES:
        if (item["name"], item["channel"]) in existing:
            continue
        db.add(
            MessageTemplate(
                user_id=user.id,
                variables=variables_used(item["subject"] + " " + item["body"]),
                **item,
            )
        )
        created += 1
    db.commit()
    return {"created": created, "total": len(DEFAULT_TEMPLATES)}


def _parse_html_metadata(html_content: str, filename: str) -> dict[str, Any]:
    """Extract metadata from HTML template."""
    # Extract title from <title> tag or first <h1>
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_content, re.IGNORECASE | re.DOTALL)
    
    name = filename.replace(".html", "").replace("_", " ").title()
    if title_match:
        name = title_match.group(1).strip()
    elif h1_match:
        name = h1_match.group(1).strip()
    
    # Extract category from filename or path
    category = "email"
    if "whatsapp" in filename.lower():
        category = "whatsapp"
    elif "linkedin" in filename.lower():
        category = "linkedin"
    elif "follow" in filename.lower():
        category = "follow_up"
    elif "intro" in filename.lower():
        category = "introduction"
    
    # Extract subject from first heading or meta
    subject = name
    subject_match = re.search(r'<meta[^>]*name=["\']subject["\'][^>]*content=["\'](.*?)["\']', html_content, re.IGNORECASE)
    if subject_match:
        subject = subject_match.group(1).strip()
    
    return {
        "name": name[:128],
        "subject": subject[:255],
        "body": html_content,
        "category": category,
    }


@router.post("/sync-gcs")
def sync_templates_from_gcs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sync HTML templates from GCS bucket kalika_enterprises/Mail_templates."""
    gcs = GCSStorage(bucket_name=GCS_BUCKET)
    if not gcs.available:
        raise HTTPException(status_code=503, detail="GCS is not available")
    
    # List HTML files in Mail_templates folder
    blobs = gcs.list_contacts(prefix=GCS_PATH)
    html_blobs = [b for b in blobs if b["name"].lower().endswith(".html")]
    
    if not html_blobs:
        return {"synced": 0, "updated": 0, "message": "No HTML templates found in GCS"}
    
    synced = 0
    updated = 0
    
    for blob_info in html_blobs:
        blob_name = blob_info["name"]
        filename = blob_name.split("/")[-1]
        
        # Download HTML content
        html_bytes = gcs.download_blob(blob_name)
        if not html_bytes:
            continue
        
        try:
            html_content = html_bytes.decode("utf-8")
        except UnicodeDecodeError:
            html_content = html_bytes.decode("latin-1")
        
        # Parse metadata
        metadata = _parse_html_metadata(html_content, filename)
        
        # Check if template already exists
        existing = (
            db.query(MessageTemplate)
            .filter(
                MessageTemplate.user_id == user.id,
                MessageTemplate.name == metadata["name"],
            )
            .first()
        )
        
        if existing:
            # Update existing template
            existing.body = metadata["body"]
            existing.subject = metadata["subject"]
            existing.channel = metadata["category"]
            db.commit()
            updated += 1
        else:
            # Create new template
            template = MessageTemplate(
                user_id=user.id,
                name=metadata["name"],
                channel=metadata["category"],
                strategy="festive",
                funnel_stage="awareness",
                subject=metadata["subject"],
                body=metadata["body"],
                variables=variables_used(metadata["subject"] + " " + metadata["body"]),
                is_active=True,
            )
            db.add(template)
            db.commit()
            synced += 1
    
    log_event(
        db,
        action="template.sync_gcs",
        actor_user_id=user.id,
        resource_type="template",
        resource_id="",
        tenant_id=user.domain,
        detail={"synced": synced, "updated": updated},
        commit=True,
    )
    
    return {
        "synced": synced,
        "updated": updated,
        "total": len(html_blobs),
        "message": f"Synced {synced} new templates, updated {updated} existing templates",
    }


@router.post("/sync-specific")
def sync_specific_templates(
    gcs_paths: list[str],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sync specific HTML templates from GCS by path."""
    gcs = GCSStorage(bucket_name=GCS_BUCKET)
    if not gcs.available:
        raise HTTPException(status_code=503, detail="GCS is not available")
    
    synced = 0
    updated = 0
    
    for gcs_path in gcs_paths:
        # Download HTML content
        html_bytes = gcs.download_blob(gcs_path)
        if not html_bytes:
            continue
        
        filename = gcs_path.split("/")[-1]
        
        try:
            html_content = html_bytes.decode("utf-8")
        except UnicodeDecodeError:
            html_content = html_bytes.decode("latin-1")
        
        # Parse metadata
        metadata = _parse_html_metadata(html_content, filename)
        
        # Check if template already exists
        existing = (
            db.query(MessageTemplate)
            .filter(
                MessageTemplate.user_id == user.id,
                MessageTemplate.name == metadata["name"],
            )
            .first()
        )
        
        if existing:
            # Update existing template
            existing.body = metadata["body"]
            existing.subject = metadata["subject"]
            existing.channel = metadata["category"]
            db.commit()
            updated += 1
        else:
            # Create new template
            template = MessageTemplate(
                user_id=user.id,
                name=metadata["name"],
                channel=metadata["category"],
                strategy="festive",
                funnel_stage="awareness",
                subject=metadata["subject"],
                body=metadata["body"],
                variables=variables_used(metadata["subject"] + " " + metadata["body"]),
                is_active=True,
            )
            db.add(template)
            db.commit()
            synced += 1
    
    return {
        "synced": synced,
        "updated": updated,
        "message": f"Synced {synced} templates, updated {updated} templates",
    }
