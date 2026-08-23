"""Admin endpoints (Spec §13, §14, §25).

Every route requires an admin token (require_admin). Provides product management, inventory
(stock updates, low/out-of-stock status, threshold-based restock suggestions), and order
management. Restock uses SQL aggregation for recent demand — no per-product query loop (§16).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..database import get_db
from ..deps import require_admin
from ..models import Order, OrderItem, Product
from ..schemas import (
    AdminOrderRow,
    AdminProductRow,
    OrderStatusUpdate,
    PageMeta,
    ProductCreate,
    ProductUpdate,
    RestockRow,
)
from ..services import inventory, order_state
from ..services.inventory import stock_status

settings = get_settings()
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

RECENT_SALES_DAYS = 30


def _row(p: Product) -> AdminProductRow:
    return AdminProductRow(
        id=p.id, name=p.name, category=p.category, price=float(p.price),
        stock_quantity=p.stock_quantity, low_stock_threshold=p.low_stock_threshold,
        eco_score=p.eco_score, is_eco_friendly=p.is_eco_friendly, stock_status=stock_status(p),
    )


# ---- Products / inventory ----
@router.get("/products", response_model=dict)
def list_products(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size),
) -> dict:
    total = db.scalar(select(func.count()).select_from(Product)) or 0
    rows = db.scalars(
        select(Product).order_by(Product.id).offset((page - 1) * limit).limit(limit)
    ).all()
    return {
        "items": [_row(p) for p in rows],
        "meta": PageMeta(page=page, limit=limit, total=total, pages=(total + limit - 1) // limit),
    }


@router.post("/products", response_model=AdminProductRow, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> AdminProductRow:
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return _row(product)


@router.patch("/products/{product_id}", response_model=AdminProductRow)
def update_product(
    product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)
) -> AdminProductRow:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    # Only write fields that were actually provided (no full-row rewrite — Spec §16).
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return _row(product)


@router.get("/inventory/restock", response_model=list[RestockRow])
def restock_recommendations(db: Session = Depends(get_db)) -> list[RestockRow]:
    """Threshold + recent-demand restock suggestions. 2 queries total (products + sales agg)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_SALES_DAYS)
    sales = dict(
        db.execute(
            select(OrderItem.product_id, func.sum(OrderItem.quantity))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.created_at >= cutoff)
            .group_by(OrderItem.product_id)
        ).all()
    )
    products = db.scalars(select(Product).order_by(Product.id)).all()

    suggestions = []
    for p in products:
        suggestion = inventory.restock_suggestion(p, int(sales.get(p.id, 0)))
        if suggestion is not None:
            suggestions.append(RestockRow(**suggestion.__dict__))
    return suggestions


# ---- Orders ----
@router.get("/orders", response_model=dict)
def list_orders(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size),
) -> dict:
    total = db.scalar(select(func.count()).select_from(Order)) or 0
    rows = db.scalars(
        select(Order).order_by(Order.created_at.desc()).offset((page - 1) * limit).limit(limit)
    ).all()
    return {
        "items": [AdminOrderRow.model_validate(o) for o in rows],
        "meta": PageMeta(page=page, limit=limit, total=total, pages=(total + limit - 1) // limit),
    }


@router.patch("/orders/{order_id}", response_model=AdminOrderRow)
def update_order_status(
    order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db)
) -> AdminOrderRow:
    """Advance an order through the state machine, keeping inventory consistent (Phase-2 §14, §15).

    Only transitions allowed from the current state are accepted. Cancelling restores stock
    exactly once (idempotent via Order.stock_deducted); forward transitions never re-deduct,
    so repeated status changes can't double-count inventory.
    """
    if payload.status not in order_state.ALL_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid status")

    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")

    if payload.status == order.status:
        return AdminOrderRow.model_validate(order)  # no-op, stay idempotent

    if not order_state.admin_can_transition(order.status, payload.status):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Cannot change order from {order.status} to {payload.status}",
        )

    if payload.status == order_state.CANCELLED:
        inventory.restore_for_order(order)  # idempotent restore

    order.status = payload.status
    db.commit()
    db.refresh(order)
    return AdminOrderRow.model_validate(order)
