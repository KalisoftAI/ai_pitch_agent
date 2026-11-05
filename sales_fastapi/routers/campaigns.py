"""Lightweight campaign system for category-wise email sending."""

from __future__ import annotations

import csv
from io import BytesIO, StringIO
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Campaign, CampaignMessage, Contact, MessageTemplate, User
from ..schemas import CampaignCreate, CampaignMessageOut, CampaignOut
from ..security import get_current_user
from ..services import GCSStorage

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

MARKETING_GCS_PATH = "sales-contacts/RECENT_marketing_list_kalika.xlsx"
ERP_GCS_PATH = "sales-contacts/customers.csv"


class ContactList(BaseModel):
    contacts: list[dict[str, Any]]
    total: int
    by_category: dict[str, int] = Field(default_factory=dict)


class CampaignStart(BaseModel):
    template_id: int
    contact_source: str  # "marketing" or "erp"
    categories: list[str] = []  # Empty means all categories


@router.post("/load-contacts")
def load_contacts_from_gcs(
    source: str,
    user: User = Depends(get_current_user),
):
    """Load contacts from GCS sources (marketing or ERP)."""
    gcs = GCSStorage(bucket_name="kalika_enterprises")
    if not gcs.available:
        raise HTTPException(status_code=503, detail="GCS is not available")
    
    contacts = []
    by_category = {}
    
    if source == "marketing":
        # Load from Excel file
        xlsx_bytes = gcs.download_blob(MARKETING_GCS_PATH)
        if not xlsx_bytes:
            raise HTTPException(status_code=404, detail="Marketing contacts file not found")
        
        try:
            import openpyxl
            wb = openpyxl.load_workbook(BytesIO(xlsx_bytes))
            ws = wb.active
            
            # Get headers from first row
            headers = [str(cell.value).strip().lower() if cell.value else "" for cell in ws[1]]
            
            # Map columns
            email_idx = next((i for i, h in enumerate(headers) if "email" in h), -1)
            category_idx = next((i for i, h in enumerate(headers) if "category" in h), -1)
            name_idx = next((i for i, h in enumerate(headers) if "name" in h), -1)
            
            for row in ws.iter_rows(min_row=2, values_only=True):
                if email_idx >= 0 and row[email_idx]:
                    email = str(row[email_idx]).strip()
                    if "@" in email:
                        category = str(row[category_idx]).strip() if category_idx >= 0 and row[category_idx] else "uncategorized"
                        name = str(row[name_idx]).strip() if name_idx >= 0 and row[name_idx] else ""
                        
                        contacts.append({
                            "email": email,
                            "category": category,
                            "name": name,
                            "source": "marketing",
                        })
                        
                        by_category[category] = by_category.get(category, 0) + 1
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse Excel: {str(e)}")
    
    elif source == "erp":
        # Load from CSV file
        csv_bytes = gcs.download_blob(ERP_GCS_PATH)
        if not csv_bytes:
            raise HTTPException(status_code=404, detail="ERP customers file not found")
        
        try:
            csv_text = csv_bytes.decode("utf-8")
            reader = csv.DictReader(StringIO(csv_text))
            
            for row in reader:
                email = row.get("email", "").strip()
                if email and "@" in email:
                    category = row.get("category", "uncategorized").strip() or "uncategorized"
                    name = row.get("name", "").strip()
                    
                    contacts.append({
                        "email": email,
                        "category": category,
                        "name": name,
                        "source": "erp",
                    })
                    
                    by_category[category] = by_category.get(category, 0) + 1
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse CSV: {str(e)}")
    
    else:
        raise HTTPException(status_code=400, detail="Invalid source. Use 'marketing' or 'erp'")
    
    return ContactList(
        contacts=contacts,
        total=len(contacts),
        by_category=by_category,
    )


@router.post("/create")
def create_campaign(
    payload: CampaignStart,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a campaign with selected template and contacts."""
    # Get template
    template = db.query(MessageTemplate).filter(
        MessageTemplate.id == payload.template_id,
        MessageTemplate.user_id == user.id,
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Load contacts
    gcs = GCSStorage(bucket_name="kalika_enterprises")
    if not gcs.available:
        raise HTTPException(status_code=503, detail="GCS is not available")
    
    contacts = []
    if payload.contact_source == "marketing":
        xlsx_bytes = gcs.download_blob(MARKETING_GCS_PATH)
        if xlsx_bytes:
            import openpyxl
            wb = openpyxl.load_workbook(BytesIO(xlsx_bytes))
            ws = wb.active
            headers = [str(cell.value).strip().lower() if cell.value else "" for cell in ws[1]]
            email_idx = next((i for i, h in enumerate(headers) if "email" in h), -1)
            category_idx = next((i for i, h in enumerate(headers) if "category" in h), -1)
            name_idx = next((i for i, h in enumerate(headers) if "name" in h), -1)
            
            for row in ws.iter_rows(min_row=2, values_only=True):
                if email_idx >= 0 and row[email_idx]:
                    email = str(row[email_idx]).strip()
                    if "@" in email:
                        category = str(row[category_idx]).strip() if category_idx >= 0 and row[category_idx] else "uncategorized"
                        if not payload.categories or category in payload.categories:
                            name = str(row[name_idx]).strip() if name_idx >= 0 and row[name_idx] else ""
                            contacts.append({"email": email, "name": name, "category": category})
    
    elif payload.contact_source == "erp":
        csv_bytes = gcs.download_blob(ERP_GCS_PATH)
        if csv_bytes:
            csv_text = csv_bytes.decode("utf-8")
            reader = csv.DictReader(StringIO(csv_text))
            for row in reader:
                email = row.get("email", "").strip()
                if email and "@" in email:
                    category = row.get("category", "uncategorized").strip() or "uncategorized"
                    if not payload.categories or category in payload.categories:
                        name = row.get("name", "").strip()
                        contacts.append({"email": email, "name": name, "category": category})
    
    if not contacts:
        raise HTTPException(status_code=400, detail="No contacts found for selected categories")
    
    # Create campaign
    campaign = Campaign(
        user_id=user.id,
        name=f"{template.name} - {payload.contact_source}",
        channel=template.channel,
        template_id=template.id,
        total=len(contacts),
        status="pending_review",
    )
    db.add(campaign)
    db.flush()
    
    # Create campaign messages
    for contact in contacts:
        # Render template
        rendered_subject = template.subject
        rendered_body = template.body
        
        # Replace variables
        for var in template.variables:
            var_name = var.strip("{{}}").strip()
            value = contact.get(var_name, "")
            rendered_subject = rendered_subject.replace(f"{{{{{var_name}}}}}", value)
            rendered_body = rendered_body.replace(f"{{{{{var_name}}}}}", value)
        
        message = CampaignMessage(
            campaign_id=campaign.id,
            user_id=user.id,
            to_address=contact["email"],
            rendered_subject=rendered_subject,
            rendered_body=rendered_body,
            status="pending_review",
        )
        db.add(message)
    
    db.commit()
    
    return {
        "campaign_id": campaign.id,
        "total_messages": len(contacts),
        "status": "pending_review",
        "message": f"Campaign created with {len(contacts)} messages",
    }


@router.get("/list")
def list_campaigns(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all campaigns for the user."""
    campaigns = db.query(Campaign).filter(
        Campaign.user_id == user.id
    ).order_by(Campaign.created_at.desc()).all()
    
    return [
        {
            "id": c.id,
            "name": c.name,
            "channel": c.channel,
            "total": c.total,
            "sent": c.sent_count,
            "status": c.status,
            "created_at": str(c.created_at),
        }
        for c in campaigns
    ]


@router.get("/{campaign_id}/messages")
def get_campaign_messages(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all messages for a campaign."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == user.id,
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    messages = db.query(CampaignMessage).filter(
        CampaignMessage.campaign_id == campaign_id
    ).all()
    
    return [
        {
            "id": m.id,
            "to": m.to_address,
            "subject": m.rendered_subject,
            "body_preview": m.rendered_body[:100] + "..." if len(m.rendered_body) > 100 else m.rendered_body,
            "status": m.status,
        }
        for m in messages
    ]


@router.post("/{campaign_id}/approve")
def approve_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve campaign for sending."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == user.id,
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "approved"
    db.commit()
    
    return {"message": "Campaign approved", "status": "approved"}


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a campaign and its messages."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == user.id,
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Delete messages
    db.query(CampaignMessage).filter(CampaignMessage.campaign_id == campaign_id).delete()
    
    # Delete campaign
    db.delete(campaign)
    db.commit()
    
    return {"message": "Campaign deleted"}
