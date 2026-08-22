"""Shared cart query (Spec §30 — single source for cart loading, no duplicated logic).

Used by the cart, orders, and carbon endpoints. One query eager-loads each line item's
product to avoid N+1 (Spec §16).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Cart, CartItem


def load_cart_items(db: Session, customer_id: int) -> list[CartItem]:
    return list(
        db.scalars(
            select(CartItem)
            .join(Cart, Cart.id == CartItem.cart_id)
            .where(Cart.customer_id == customer_id)
            .options(selectinload(CartItem.product))
            .order_by(CartItem.id)
        ).all()
    )
