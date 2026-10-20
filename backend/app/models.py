"""SQLAlchemy ORM models (Spec §5).

Only tables required by a requirement exist. Indexes are declared on foreign keys and on the
columns used for filtering/sorting in hot paths (catalog category/eco filters, order lookups
by customer and date) — this is the energy-efficient-DB requirement (Spec §16, G2).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Email verification (Spec Phase-2 §1): an account stays unverified until a delivery code is
    # confirmed; unverified accounts cannot access protected customer functionality.
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Justified deviation (matrix Note C): admin authorization for R9 / Spec §25.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    image_url: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(String(2000), default="")
    category: Mapped[str] = mapped_column(String(80), index=True)  # hot filter column
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[float] = mapped_column(Float, default=0.5)  # kg, for delivery carbon
    eco_score: Mapped[int] = mapped_column(Integer, default=50)  # 0..100 sustainability
    carbon_factor: Mapped[float] = mapped_column(Float, default=1.0)  # kg CO2e per unit
    is_eco_friendly: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Justified deviation (matrix Note D): per-product low-stock threshold for R8.
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ProductRating(Base):
    __tablename__ = "product_ratings"
    __table_args__ = (
        UniqueConstraint("customer_id", "product_id", name="uq_customer_product_rating"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), unique=True, index=True
    )
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    cart: Mapped["Cart"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), index=True  # report grouping by customer
    )
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    delivery_method: Mapped[str] = mapped_column(String(40))
    delivery_distance: Mapped[float] = mapped_column(Float)  # km
    carbon_impact: Mapped[float] = mapped_column(Float)  # kg CO2e total, stored for reporting (§12)
    # Delivery component stored separately so the "reduction vs Express" report is a clean
    # aggregation, not a fragile weight reconstruction (Spec §15; matrix Note F).
    delivery_carbon: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="Pending Payment", index=True)
    # Idempotency guard for the inventory lifecycle (Spec Phase-2 §13, §14): stock is deducted
    # exactly once (on payment) and restored exactly once (on cancellation). Repeated status
    # updates check this flag and never double-deduct / double-restore.
    stock_deducted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Paystack transaction reference; the verify endpoint looks the order up by this (Spec §11).
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True  # time-series reports
    )

    customer: Mapped["Customer"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class RecommendationInteraction(Base):
    """Matrix Note E: created only because R5 lists purchase history / views as inputs.

    interaction_type is 'view' or 'purchase'. No other analytics are stored (Spec §5).
    """

    __tablename__ = "recommendation_interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    interaction_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VerificationCode(Base):
    """Short-lived, single-use codes for email verification / login / password reset.

    Spec Phase-2 §2: codes expire, are single-use, are never stored in plaintext (only a
    SHA-256 hash is kept), and attempts are capped. `purpose` separates the flows so a reset
    code cannot be replayed as a login code.
    """

    __tablename__ = "verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(20), index=True)  # email_verify | password_reset
    code_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 hex of the 6-digit code
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
