"""Product master, rate approvals and rate calculator."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..erp_sync import rate_calculator
from ..models import Product, ProductRate, User
from ..security import get_current_user, is_admin_user, require_roles

router = APIRouter(prefix="/catalog", tags=["catalog"])


class ProductIn(BaseModel):
    code: str = Field(default="", max_length=64)
    name: str = Field(..., min_length=2, max_length=255)
    category: str = Field(default="", max_length=128)
    unit: str = Field(default="kg", max_length=32)
    description: str = Field(default="", max_length=10_000)
    is_active: bool = True


class ProductUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, min_length=2, max_length=255)
    category: str | None = Field(default=None, max_length=128)
    unit: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=10_000)
    is_active: bool | None = None


class RateIn(BaseModel):
    product_id: int = Field(..., ge=1)
    rate: float = Field(..., gt=0, le=1_000_000)
    currency: str = Field(default="INR", max_length=8)
    unit: str = Field(default="kg", max_length=32)
    effective_date: str = Field(default="", max_length=10)
    notes: str = Field(default="", max_length=5_000)


class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]
    notes: str = Field(default="", max_length=5_000)


class QuoteIn(BaseModel):
    product_id: int = Field(..., ge=1)
    rate: float | None = Field(default=None, gt=0, le=1_000_000)
    micron: float = Field(default=23, gt=1, le=300)
    width_mm: float = Field(default=500, gt=50, le=5000)
    length_m: float = Field(default=1000, gt=10, le=20000)
    density: float = Field(default=0.92, gt=0.5, le=1.6)
    waste_pct: float = Field(default=2, ge=0, le=30)
    conversion_cost_per_kg: float = Field(default=18, ge=0, le=500)
    margin_pct: float = Field(default=8, ge=0, le=100)


def _product_out(product: Product) -> dict:
    return {
        "id": product.id,
        "code": product.code,
        "name": product.name,
        "category": product.category,
        "unit": product.unit,
        "description": product.description,
        "is_active": product.is_active,
        "created_at": str(product.created_at),
        "updated_at": str(product.updated_at),
    }


def _rate_out(rate: ProductRate, product: Product | None = None) -> dict:
    return {
        "id": rate.id,
        "product_id": rate.product_id,
        "product_name": product.name if product else "",
        "product_code": product.code if product else "",
        "rate": rate.rate,
        "currency": rate.currency,
        "unit": rate.unit,
        "effective_date": rate.effective_date,
        "status": rate.status,
        "submitted_by": rate.submitted_by,
        "approved_by": rate.approved_by,
        "notes": rate.notes,
        "reviewed_at": str(rate.reviewed_at) if rate.reviewed_at else None,
        "created_at": str(rate.created_at),
        "updated_at": str(rate.updated_at),
    }


def _own_product(product: Product | None, user: User) -> Product:
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if not is_admin_user(user) and product.user_id not in (0, user.id):
        raise HTTPException(status_code=403, detail="Product belongs to another workspace")
    return product


def _latest_approved(db: Session, product_id: int) -> ProductRate | None:
    return (
        db.query(ProductRate)
        .filter(ProductRate.product_id == product_id, ProductRate.status == "approved")
        .order_by(ProductRate.effective_date.desc(), ProductRate.id.desc())
        .first()
    )


@router.get("/summary")
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    products = db.query(Product)
    rates = db.query(ProductRate)
    return {
        "products": products.count(),
        "active_products": products.filter(Product.is_active.is_(True)).count(),
        "pending_rates": rates.filter(ProductRate.status == "pending").count(),
        "approved_rates": rates.filter(ProductRate.status == "approved").count(),
        "rejected_rates": rates.filter(ProductRate.status == "rejected").count(),
        "latest_rate_date": (
            rates.order_by(ProductRate.effective_date.desc()).first().effective_date
            if rates.count()
            else ""
        ),
    }


@router.get("/products")
def list_products(
    q: str = "",
    category: str = "",
    active_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Product)
    if q:
        like = f"%{q}%"
        query = query.filter(
            Product.name.ilike(like) | Product.code.ilike(like) | Product.category.ilike(like)
        )
    if category:
        query = query.filter(Product.category == category)
    if active_only:
        query = query.filter(Product.is_active.is_(True))
    return [_product_out(product) for product in query.order_by(Product.name.asc()).all()]


@router.post("/products", status_code=201)
def create_product(
    payload: ProductIn, user: User = Depends(require_roles("sales")), db: Session = Depends(get_db)
):
    code = payload.code.strip() or payload.name.strip().lower().replace(" ", "-")[:64]
    exists = db.query(Product).filter(Product.code == code).first()
    if exists:
        raise HTTPException(status_code=409, detail="Product code already exists")
    product = Product(user_id=user.id, code=code, **payload.model_dump(exclude={"code"}))
    db.add(product)
    db.commit()
    db.refresh(product)
    return _product_out(product)


@router.patch("/products/{product_id}")
def update_product(
    product_id: int,
    payload: ProductUpdate,
    user: User = Depends(require_roles("sales")),
    db: Session = Depends(get_db),
):
    product = _own_product(db.get(Product, product_id), user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    product.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(product)
    return _product_out(product)


@router.get("/products/{product_id}/rates")
def product_rates(
    product_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    rows = (
        db.query(ProductRate)
        .filter(ProductRate.product_id == product_id)
        .order_by(ProductRate.id.desc())
        .limit(limit)
        .all()
    )
    return [_rate_out(rate, product) for rate in rows]


@router.get("/rates")
def list_rates(
    product_id: int | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(ProductRate)
    if product_id:
        query = query.filter(ProductRate.product_id == product_id)
    if status:
        query = query.filter(ProductRate.status == status)
    rows = query.order_by(ProductRate.id.desc()).limit(limit).all()
    products = {p.id: p for p in db.query(Product).all()}
    return [_rate_out(rate, products.get(rate.product_id)) for rate in rows]


@router.post("/rates", status_code=201)
def submit_rate(
    payload: RateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    effective = payload.effective_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rate = ProductRate(
        user_id=user.id,
        product_id=product.id,
        rate=payload.rate,
        currency=payload.currency,
        unit=payload.unit or product.unit,
        effective_date=effective,
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
    user: User = Depends(require_roles("sales")),
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
    rate.reviewed_at = datetime.now(timezone.utc)
    if payload.notes:
        rate.notes = payload.notes
    db.commit()
    product = db.get(Product, rate.product_id)
    return _rate_out(rate, product)


@router.get("/rate-today")
def rate_today(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = (
        db.query(ProductRate)
        .filter(ProductRate.effective_date == today)
        .order_by(ProductRate.id.desc())
        .all()
    )
    products = {p.id: p for p in db.query(Product).all()}
    pending = (
        db.query(ProductRate)
        .filter(ProductRate.status == "pending")
        .order_by(ProductRate.id.desc())
        .limit(50)
        .all()
    )
    return {
        "date": today,
        "today": [_rate_out(rate, products.get(rate.product_id)) for rate in rows],
        "pending_count": db.query(ProductRate).filter(ProductRate.status == "pending").count(),
        "pending": [_rate_out(rate, products.get(rate.product_id)) for rate in pending],
    }


@router.post("/quote")
def quote(payload: QuoteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    approved = _latest_approved(db, product.id)
    rate = payload.rate or (approved.rate if approved else 0)
    if not rate:
        raise HTTPException(
            status_code=400, detail="No approved rate yet; submit a rate or pass rate explicitly"
        )
    result = rate_calculator(
        polymer_rate=rate,
        micron=payload.micron,
        width_mm=payload.width_mm,
        length_m=payload.length_m,
        density=payload.density,
        waste_pct=payload.waste_pct,
        conversion_cost_per_kg=payload.conversion_cost_per_kg,
        margin_pct=payload.margin_pct,
    )
    return {
        "product": _product_out(product),
        "rate_source": "manual" if payload.rate else "approved",
        "approved_rate_id": approved.id if approved and not payload.rate else None,
        "approved_rate": approved.rate if approved else None,
        **result,
    }
