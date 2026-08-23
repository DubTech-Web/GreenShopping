"""Inventory optimization (Spec §13, R8).

A simple, deterministic demand/threshold calculation — no predictive ML (Spec §13). A product
is flagged for restock when current stock is at/below its threshold, or when recent demand
(units sold in a recent window) would exhaust stock soon. Explainable, cheap, and computed
from data already in the database.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models import Order, Product

OUT_OF_STOCK = "out_of_stock"
LOW_STOCK = "low_stock"
IN_STOCK = "in_stock"


class InsufficientStockError(Exception):
    """Raised when an order cannot be committed because a product ran out of stock.

    Carries the product name so the router can return a clear 409 (Spec §26). Business logic
    stays free of HTTP concerns.
    """

    def __init__(self, product_name: str) -> None:
        super().__init__(f"Insufficient stock for {product_name}")
        self.product_name = product_name


def stock_status(product: Product) -> str:
    if product.stock_quantity <= 0:
        return OUT_OF_STOCK
    if product.stock_quantity <= product.low_stock_threshold:
        return LOW_STOCK
    return IN_STOCK


def deduct_for_order(order: Order) -> None:
    """Deduct each line's quantity from stock exactly once (Spec Phase-2 §13).

    Idempotent: if the order's stock was already committed, this is a no-op — so a repeated
    admin status change or a re-verified payment can never double-deduct. Re-validates stock
    at commit time and raises InsufficientStockError before mutating anything, so a partial
    deduction can't occur (the caller runs this inside a transaction).

    Requires order.items and each item.product to be loaded by the caller.
    """
    if order.stock_deducted:
        return
    for item in order.items:
        if item.quantity > item.product.stock_quantity:
            raise InsufficientStockError(item.product.name)
    for item in order.items:
        item.product.stock_quantity -= item.quantity
    order.stock_deducted = True


def restore_for_order(order: Order) -> None:
    """Return each line's quantity to stock exactly once on cancellation (Spec Phase-2 §14).

    Idempotent: only restores if stock was previously committed, so cancelling an unpaid order
    (never deducted) does not inflate inventory, and a second cancellation is a no-op.
    """
    if not order.stock_deducted:
        return
    for item in order.items:
        item.product.stock_quantity += item.quantity
    order.stock_deducted = False


@dataclass(frozen=True)
class RestockSuggestion:
    product_id: int
    name: str
    stock_quantity: int
    low_stock_threshold: int
    recent_units_sold: int
    status: str
    suggested_reorder_qty: int
    reason: str


def restock_suggestion(product: Product, recent_units_sold: int) -> RestockSuggestion | None:
    """Return a suggestion when stock is low/out or recent demand outpaces stock, else None.

    Reorder target = max(threshold*2, recent demand) so a restock clears the low mark and
    covers observed demand. Deterministic and transparent (Spec §13).
    """
    status = stock_status(product)
    demand_risk = recent_units_sold > product.stock_quantity

    if status == IN_STOCK and not demand_risk:
        return None

    target = max(product.low_stock_threshold * 2, recent_units_sold)
    reorder = max(target - product.stock_quantity, 0)

    if status == OUT_OF_STOCK:
        reason = "Out of stock."
    elif status == LOW_STOCK:
        reason = f"At/below low-stock threshold ({product.low_stock_threshold})."
    else:
        reason = f"Recent demand ({recent_units_sold}) exceeds current stock."

    return RestockSuggestion(
        product_id=product.id,
        name=product.name,
        stock_quantity=product.stock_quantity,
        low_stock_threshold=product.low_stock_threshold,
        recent_units_sold=recent_units_sold,
        status=status,
        suggested_reorder_qty=reorder,
        reason=reason,
    )
