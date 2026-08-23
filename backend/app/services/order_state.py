"""Order state machine (Spec Phase-2 §15).

One authoritative definition of order statuses and the transitions allowed between them, so
the customer flow (checkout, cancel), the payment flow (verify -> Paid), and the admin flow
(fulfilment) all agree. Keeping this in one module prevents the states from drifting apart.

Lifecycle:

    Pending Payment ──pay──▶ Paid ──▶ Processing ──▶ Shipped ──▶ Delivered
          │                   │            │
          └──────────── Cancelled ◀────────┘

Stock is *committed* (deducted from inventory) at the moment an order becomes Paid, and only
then. Cancellation from any stock-committed state restores it. Both happen exactly once,
guarded by Order.stock_deducted (Spec Phase-2 §13, §14).
"""
from __future__ import annotations

PENDING_PAYMENT = "Pending Payment"
PAID = "Paid"
PROCESSING = "Processing"
SHIPPED = "Shipped"
DELIVERED = "Delivered"
CANCELLED = "Cancelled"

ALL_STATUSES: tuple[str, ...] = (
    PENDING_PAYMENT, PAID, PROCESSING, SHIPPED, DELIVERED, CANCELLED,
)

# Statuses in which inventory has been (or should be) deducted for the order.
STOCK_COMMITTED_STATES: frozenset[str] = frozenset({PAID, PROCESSING, SHIPPED, DELIVERED})

# Admin-driven forward transitions. Payment (not admin) performs Pending Payment -> Paid.
ADMIN_TRANSITIONS: dict[str, frozenset[str]] = {
    PENDING_PAYMENT: frozenset({CANCELLED}),
    PAID: frozenset({PROCESSING, CANCELLED}),
    PROCESSING: frozenset({SHIPPED, CANCELLED}),
    SHIPPED: frozenset({DELIVERED}),
    DELIVERED: frozenset(),
    CANCELLED: frozenset(),
}

# States a customer (or admin) may cancel from (Spec Phase-2 §15).
CANCELLABLE_STATES: frozenset[str] = frozenset({PENDING_PAYMENT, PAID, PROCESSING})


def admin_can_transition(current: str, target: str) -> bool:
    return target in ADMIN_TRANSITIONS.get(current, frozenset())


def can_cancel(current: str) -> bool:
    return current in CANCELLABLE_STATES
