"""Pydantic request/response schemas (Spec §17, §30).

DTOs are intentionally separate from ORM models so responses carry only the fields a screen
needs — smaller payloads, no accidental column leakage.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---- Auth ----
class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendCodeRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)


class ProfileUpdate(BaseModel):
    """Only the name is editable; email is the login identity and account status is system-set."""

    name: str = Field(min_length=1, max_length=120)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """Generic acknowledgement for flows that must not leak state (e.g. code sent).

    ``dev_code`` is populated ONLY in non-production when Resend is disabled, so a developer can
    complete the flow without a mail provider. It is never present in production (Spec §2, §5).
    """

    message: str
    dev_code: str | None = None
    cooldown_seconds: int | None = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    is_admin: bool
    is_verified: bool
    created_at: datetime


# ---- Products (compact summary for lists vs. full detail) ----
class ProductSummary(BaseModel):
    """List payload — only what a product card renders (Spec §17)."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    image_url: str
    category: str
    price: float
    stock_quantity: int
    eco_score: int
    is_eco_friendly: bool


class ProductDetail(ProductSummary):
    description: str
    weight: float
    carbon_factor: float
    low_stock_threshold: int


# ---- Recommendations (bundled into product detail — one request, Spec §17) ----
class RecommendationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    image_url: str
    category: str
    price: float
    eco_score: int
    is_eco_friendly: bool
    carbon_factor: float
    score: float
    reason: str


class ProductDetailWithRecs(ProductDetail):
    """Product page payload: the product + similar items + a greener alternative."""

    recommendations: list[RecommendationItem] = []
    eco_alternative: RecommendationItem | None = None


class PageMeta(BaseModel):
    page: int
    limit: int
    total: int
    pages: int


class ProductPage(BaseModel):
    items: list[ProductSummary]
    meta: PageMeta


# ---- Cart ----
class AddCartItem(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=999)


class UpdateCartItem(BaseModel):
    quantity: int = Field(ge=1, le=999)


class CartItemResponse(BaseModel):
    id: int
    product_id: int
    name: str
    price: float
    quantity: int
    stock_quantity: int
    line_total: float


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    subtotal: float
    item_count: int


# ---- Orders ----
class CarbonBreakdown(BaseModel):
    product_carbon: float
    delivery_carbon: float
    total_carbon: float
    package_weight: float
    unit: str = "kg CO2e"
    is_estimate: bool = True


class CheckoutRequest(BaseModel):
    delivery_method: str = Field(description="Delivery option key: eco | standard | express")
    delivery_distance: float = Field(gt=0, le=20000, description="Distance in km")


# ---- Carbon estimate preview (single call powers the whole checkout screen) ----
class EstimateRequest(BaseModel):
    delivery_distance: float = Field(gt=0, le=20000, description="Distance in km")


class DeliveryOptionEstimate(BaseModel):
    key: str
    label: str
    speed: str
    cost: float
    emission_factor: float
    delivery_carbon: float
    total_carbon: float  # product_carbon + this option's delivery_carbon


class EstimateResponse(BaseModel):
    product_carbon: float
    package_weight: float
    options: list[DeliveryOptionEstimate]
    recommended: str  # option key with lowest total carbon
    reason: str
    unit: str = "kg CO2e"
    is_estimate: bool = True


class OrderItemResponse(BaseModel):
    product_id: int
    name: str
    quantity: int
    unit_price: float
    line_total: float


class OrderResponse(BaseModel):
    id: int
    status: str
    total_amount: float
    delivery_method: str
    delivery_distance: float
    carbon_impact: float
    created_at: datetime
    items: list[OrderItemResponse]


class OrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    total_amount: float
    delivery_method: str
    carbon_impact: float
    created_at: datetime


# ---- Payments (Paystack, fixed ₦100 demo charge — Spec Phase-2 §9–§12) ----
class PaymentInitRequest(BaseModel):
    order_id: int
    callback_url: str | None = None


class PaymentInitResponse(BaseModel):
    reference: str
    amount_kobo: int  # backend-authoritative; always PAYMENT_AMOUNT_KOBO, never the cart total
    public_key: str
    email: EmailStr
    simulated: bool  # True in dev/simulation mode (no real charge)
    authorization_url: str | None = None
    access_code: str | None = None


class PaymentVerifyRequest(BaseModel):
    reference: str = Field(min_length=1, max_length=100)


# ---- Admin: product management, order status, inventory (Spec §13, §14) ----
class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    image_url: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=2000)
    category: str = Field(min_length=1, max_length=80)
    price: float = Field(gt=0)
    stock_quantity: int = Field(ge=0)
    weight: float = Field(gt=0, description="kg")
    eco_score: int = Field(ge=0, le=100)
    carbon_factor: float = Field(ge=0, description="kg CO2e per unit")
    is_eco_friendly: bool = False
    low_stock_threshold: int = Field(default=5, ge=0)


class ProductUpdate(BaseModel):
    """All fields optional — only provided fields are changed (no full-row rewrite)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    image_url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    price: float | None = Field(default=None, gt=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    weight: float | None = Field(default=None, gt=0)
    eco_score: int | None = Field(default=None, ge=0, le=100)
    carbon_factor: float | None = Field(default=None, ge=0)
    is_eco_friendly: bool | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0)


class AdminProductRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    price: float
    stock_quantity: int
    low_stock_threshold: int
    eco_score: int
    is_eco_friendly: bool
    stock_status: str  # in_stock | low_stock | out_of_stock


class OrderStatusUpdate(BaseModel):
    status: str = Field(description="Pending | Processing | Shipped | Delivered | Cancelled")


class AdminOrderRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: int
    status: str
    total_amount: float
    delivery_method: str
    carbon_impact: float
    created_at: datetime


class RestockRow(BaseModel):
    product_id: int
    name: str
    stock_quantity: int
    low_stock_threshold: int
    recent_units_sold: int
    status: str
    suggested_reorder_qty: int
    reason: str


# ---- Reports & dashboard (Spec §14, §15) ----
class DashboardMetrics(BaseModel):
    total_sales: float
    total_orders: int
    total_products: int
    low_stock_products: int
    eco_delivery_percentage: float
    total_estimated_co2: float


class NamedValue(BaseModel):
    name: str
    value: float


class BestSeller(BaseModel):
    product_id: int
    name: str
    units_sold: int
    revenue: float


class SalesReport(BaseModel):
    total_sales: float
    total_orders: int
    best_sellers: list[BestSeller]
    sales_by_category: list[NamedValue]


class SustainabilityReport(BaseModel):
    total_estimated_co2: float
    average_co2_per_order: float
    eco_delivery_count: int
    eco_delivery_percentage: float
    eco_products_sold_units: int
    estimated_co2_saved_vs_express: float
    unit: str = "kg CO2e"
    is_estimate: bool = True
