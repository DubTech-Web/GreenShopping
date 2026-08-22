"""Order processing endpoints (Spec §9, R4).

Checkout runs as ONE transaction: validate stock -> compute carbon -> create order + items
-> decrement inventory -> commit. Any failure rolls the whole thing back so stock can never
drift (Spec §9, §26). Payment is simulated (Spec §9). Carbon is computed server-side and
stored on the order for reporting (Spec §12).

Order listing eager-loads items to avoid N+1 queries (Spec §16).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_customer
from ..models import Customer, Order, OrderItem, RecommendationInteraction
from ..schemas import (
    CheckoutRequest,
    OrderItemResponse,
    OrderResponse,
    OrderSummary,
)
from ..services import carbon
from ..services.cart_query import load_cart_items
from ..services.delivery import get_option

router = APIRouter(prefix="/api/orders", tags=["orders"])

VALID_STATUSES = ("Pending", "Processing", "Shipped", "Delivered", "Cancelled")


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
) -> OrderResponse:
    option = get_option(payload.delivery_method)
    if option is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown delivery method")

    items = load_cart_items(db, customer.id)
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    # Re-validate stock at checkout time (cart may be stale) before any write.
    for item in items:
        if item.quantity > item.product.stock_quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insufficient stock for {item.product.name}",
            )

    estimate = carbon.estimate_order_carbon(
        product_items=[(item.product.carbon_factor, item.quantity) for item in items],
        weight_items=[(item.product.weight, item.quantity) for item in items],
        distance_km=payload.delivery_distance,
        option=option,
    )
    total_amount = round(sum(float(i.product.price) * i.quantity for i in items), 2)

    order = Order(
        customer_id=customer.id,
        total_amount=total_amount,
        delivery_method=option.key,
        delivery_distance=payload.delivery_distance,
        carbon_impact=estimate["total_carbon"],
        delivery_carbon=estimate["delivery_carbon"],
        status="Pending",
    )
    db.add(order)
    db.flush()  # get order.id

    response_items: list[OrderItemResponse] = []
    for item in items:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.product.price,
            )
        )
        item.product.stock_quantity -= item.quantity  # reduce inventory (Spec §9, §13)
        # Record purchase signal for the recommender (Spec §10 history input; matrix Note E).
        db.add(
            RecommendationInteraction(
                customer_id=customer.id,
                product_id=item.product_id,
                interaction_type="purchase",
            )
        )
        response_items.append(
            OrderItemResponse(
                product_id=item.product_id,
                name=item.product.name,
                quantity=item.quantity,
                unit_price=float(item.product.price),
                line_total=round(float(item.product.price) * item.quantity, 2),
            )
        )

    # Empty the cart now that it has become an order.
    for item in items:
        db.delete(item)

    db.commit()
    db.refresh(order)

    return OrderResponse(
        id=order.id,
        status=order.status,
        total_amount=float(order.total_amount),
        delivery_method=order.delivery_method,
        delivery_distance=order.delivery_distance,
        carbon_impact=order.carbon_impact,
        created_at=order.created_at,
        items=response_items,
    )


@router.get("", response_model=list[OrderSummary])
def list_orders(
    db: Session = Depends(get_db), customer: Customer = Depends(get_current_customer)
) -> list[Order]:
    return db.scalars(
        select(Order).where(Order.customer_id == customer.id).order_by(Order.created_at.desc())
    ).all()


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
) -> OrderResponse:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.customer_id == customer.id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    return OrderResponse(
        id=order.id,
        status=order.status,
        total_amount=float(order.total_amount),
        delivery_method=order.delivery_method,
        delivery_distance=order.delivery_distance,
        carbon_impact=order.carbon_impact,
        created_at=order.created_at,
        items=[
            OrderItemResponse(
                product_id=oi.product_id,
                name=oi.product.name,
                quantity=oi.quantity,
                unit_price=float(oi.unit_price),
                line_total=round(float(oi.unit_price) * oi.quantity, 2),
            )
            for oi in order.items
        ],
    )
