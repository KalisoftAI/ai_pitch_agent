"""Public customer forms and the authenticated link/submission manager."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..contact_validation import normalize_email, normalize_phone
from ..database import get_db
from ..outreach_forms import get_form_links, save_form_links, submit_customer_form
from ..schemas import (
    CustomerFeedbackIn,
    CustomerFormOut,
    OutreachFormLinksIn,
    OutreachFormLinksOut,
    ProductReviewIn,
)
from ..security import get_current_user

router = APIRouter(tags=["outreach-forms"])


@router.get("/forms/config", response_model=OutreachFormLinksOut)
def public_form_config(db: Session = Depends(get_db)):
    return get_form_links(db)


@router.post("/public/forms/feedback", status_code=201, response_model=CustomerFormOut)
def submit_feedback_form(payload: CustomerFeedbackIn, db: Session = Depends(get_db)):
    fields: dict[str, Any] = payload.model_dump()
    fields["email"] = normalize_email(fields.get("email"))
    fields["phone"] = normalize_phone(fields.get("phone"))
    entry = submit_customer_form(db, "customer_feedback", fields)
    return CustomerFormOut(id=entry.id, category=entry.category, created_at=entry.created_at)


@router.post("/public/forms/review", status_code=201, response_model=CustomerFormOut)
def submit_review_form(payload: ProductReviewIn, db: Session = Depends(get_db)):
    fields: dict[str, Any] = payload.model_dump()
    fields["email"] = normalize_email(fields.get("email"))
    fields["phone"] = normalize_phone(fields.get("phone"))
    entry = submit_customer_form(db, "product_review", fields)
    return CustomerFormOut(id=entry.id, category=entry.category, created_at=entry.created_at)


@router.get("/outreach-forms/links", response_model=OutreachFormLinksOut)
def outreach_form_links(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return get_form_links(db)


@router.put("/outreach-forms/links", response_model=OutreachFormLinksOut)
def update_outreach_form_links(
    payload: OutreachFormLinksIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    values = payload.model_dump(exclude_none=True)
    try:
        return save_form_links(db, values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/outreach-forms/submissions")
def outreach_form_submissions(
    kind: str | None = Query(default=None, description="customer_feedback or product_review"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    from ..models import Feedback

    categories = ["customer_feedback", "product_review"]
    if kind in categories:
        categories = [kind]
    rows = (
        db.query(Feedback)
        .filter(Feedback.user_id == user.id, Feedback.category.in_(categories))
        .order_by(Feedback.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "category": row.category,
            "rating": row.rating,
            "message": row.message,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]
