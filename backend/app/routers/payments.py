"""Payment endpoints — Paystack, fixed ₦100 demo charge (Spec Phase-2 §9–§12).

    POST /api/payments/init    {order_id}   -> reference + public key + fixed amount
    POST /api/payments/verify  {reference}  -> verifies server-side, then commits the order

Security invariants (Spec §12):
- The amount is set by the backend (``PAYMENT_AMOUNT_KOBO``); nothing from the request body
  can change what is charged.
- The order becomes Paid — and inventory is deducted — only after ``payments.verify`` confirms
  the transaction with Paystack. Reaching the payment page is not enough.
- Payment commit runs as one transaction: mark Paid + deduct stock + clear cart. Any failure
  rolls the whole thing back, so inventory can never drift (Spec Phase-2 §18).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_customer
from ..models import Cart, CartItem, Customer, Order, OrderItem, RecommendationInteraction
from ..schemas import (
    OrderItemResponse,
    OrderResponse,
    PaymentInitRequest,
    PaymentInitResponse,
    PaymentVerifyRequest,
)
from ..services import email as email_service, inventory, order_state
from ..services import payments as paystack

router = APIRouter(prefix="/api/payments", tags=["payments"])


def _load_owned_order(db: Session, order_id: int, customer_id: int) -> Order:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.customer_id == customer_id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.post("/init", response_model=PaymentInitResponse)
def init_payment(
    payload: PaymentInitRequest,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
) -> PaymentInitResponse:
    order = _load_owned_order(db, payload.order_id, customer.id)
    if order.status != order_state.PENDING_PAYMENT:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Order is not awaiting payment (it is {order.status})"
        )

    init = paystack.initialize(
        email=customer.email,
        order_id=order.id,
        callback_url=payload.callback_url,
    )
    order.payment_reference = init.reference  # so verify can find this order by reference
    db.commit()

    return PaymentInitResponse(
        reference=init.reference,
        amount_kobo=init.amount_kobo,
        public_key=init.public_key,
        email=init.email,
        simulated=init.simulated,
        authorization_url=init.authorization_url,
        access_code=init.access_code,
    )


@router.post("/verify", response_model=OrderResponse)
def verify_payment(
    payload: PaymentVerifyRequest,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
) -> OrderResponse:
    order = db.scalar(
        select(Order)
        .where(Order.payment_reference == payload.reference, Order.customer_id == customer.id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Payment reference not found")

    # Idempotent: verifying an already-paid order just returns it (no second deduction, §14).
    if order.status != order_state.PENDING_PAYMENT:
        return _order_response(order)

    if not paystack.verify(payload.reference):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, detail="Payment not confirmed")

    # --- One transaction: commit the order + inventory + cart (Spec Phase-2 §18) ---
    try:
        inventory.deduct_for_order(order)  # raises if stock ran out between checkout and payment
    except inventory.InsufficientStockError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    order.status = order_state.PAID
    for item in order.items:
        db.add(
            RecommendationInteraction(
                customer_id=customer.id,
                product_id=item.product_id,
                interaction_type="purchase",  # history signal for the recommender (Spec §10)
            )
        )
    # Empty the cart now that it has become a paid order.
    for cart_item in db.scalars(
        select(CartItem).join(Cart, Cart.id == CartItem.cart_id).where(Cart.customer_id == customer.id)
    ):
        db.delete(cart_item)

    db.commit()
    db.refresh(order)

    # Dispatch itemized order confirmation email
    email_service.send_order_confirmation_email(order, customer.email)

    return _order_response(order)


def _order_response(order: Order) -> OrderResponse:
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
