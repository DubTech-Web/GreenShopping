"""Reports & dashboard (Spec §14, §15, §16, R9/R10).

Every figure is computed with SQL aggregation (SUM/COUNT/AVG/GROUP BY). Rows are aggregated
in SQLite and never pulled into Python to be totalled (Spec §15, §16, §21). Admin only.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import Order, OrderItem, Product
from ..schemas import (
    BestSeller,
    DashboardMetrics,
    NamedValue,
    SalesReport,
    SustainabilityReport,
)
from ..services import order_state
from ..services.delivery import DELIVERY_OPTIONS, get_option

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(require_admin)])

_EXPRESS_FACTOR = get_option("express").emission_factor
BEST_SELLERS_LIMIT = 5

# Reports count only orders whose payment succeeded (stock-committed). Provisional
# "Pending Payment" orders and "Cancelled" orders are excluded so figures reflect real,
# realized sales and their carbon (Spec Phase-2 §15; reporting §15).
COUNTED_STATES = tuple(order_state.STOCK_COMMITTED_STATES)


@router.get("/dashboard", response_model=DashboardMetrics)
def dashboard(db: Session = Depends(get_db)) -> DashboardMetrics:
    """Whole dashboard in 2 aggregate queries (Spec §16, §21).

    Naive: one query per metric (6+). Optimized: conditional aggregates fold the order metrics
    into a single row, and the product metrics into another — 2 queries total.
    """
    o = db.execute(
        select(
            func.coalesce(func.sum(Order.total_amount), 0.0),
            func.count(Order.id),
            func.coalesce(func.sum(Order.carbon_impact), 0.0),
            func.coalesce(func.sum(case((Order.delivery_method == "eco", 1), else_=0)), 0),
        ).where(Order.status.in_(COUNTED_STATES))
    ).one()
    total_sales, total_orders, total_co2, eco_orders = o

    p = db.execute(
        select(
            func.count(Product.id),
            func.coalesce(
                func.sum(case((Product.stock_quantity <= Product.low_stock_threshold, 1), else_=0)), 0
            ),
        )
    ).one()
    total_products, low_stock = p

    eco_pct = round(100.0 * eco_orders / total_orders, 1) if total_orders else 0.0
    return DashboardMetrics(
        total_sales=round(float(total_sales), 2),
        total_orders=int(total_orders),
        total_products=int(total_products),
        low_stock_products=int(low_stock),
        eco_delivery_percentage=eco_pct,
        total_estimated_co2=round(float(total_co2), 3),
    )


@router.get("/sales", response_model=SalesReport)
def sales(db: Session = Depends(get_db)) -> SalesReport:
    total_sales = db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0.0)).where(Order.status.in_(COUNTED_STATES))
    )
    total_orders = db.scalar(
        select(func.count()).select_from(Order).where(Order.status.in_(COUNTED_STATES))
    ) or 0

    # Best sellers: aggregate order_items, join product name. GROUP BY + ORDER BY + LIMIT.
    best_rows = db.execute(
        select(
            OrderItem.product_id,
            Product.name,
            func.sum(OrderItem.quantity).label("units"),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("revenue"),
        )
        .join(Product, Product.id == OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status.in_(COUNTED_STATES))
        .group_by(OrderItem.product_id, Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(BEST_SELLERS_LIMIT)
    ).all()

    by_category = db.execute(
        select(
            Product.category,
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("revenue"),
        )
        .join(Product, Product.id == OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status.in_(COUNTED_STATES))
        .group_by(Product.category)
        .order_by(func.sum(OrderItem.quantity * OrderItem.unit_price).desc())
    ).all()

    return SalesReport(
        total_sales=round(float(total_sales), 2),
        total_orders=total_orders,
        best_sellers=[
            BestSeller(product_id=r.product_id, name=r.name, units_sold=int(r.units),
                       revenue=round(float(r.revenue), 2))
            for r in best_rows
        ],
        sales_by_category=[
            NamedValue(name=r.category, value=round(float(r.revenue), 2)) for r in by_category
        ],
    )


@router.get("/sustainability", response_model=SustainabilityReport)
def sustainability(db: Session = Depends(get_db)) -> SustainabilityReport:
    total_orders = db.scalar(
        select(func.count()).select_from(Order).where(Order.status.in_(COUNTED_STATES))
    ) or 0
    total_co2 = float(db.scalar(
        select(func.coalesce(func.sum(Order.carbon_impact), 0.0)).where(Order.status.in_(COUNTED_STATES))
    ))
    avg_co2 = float(db.scalar(
        select(func.coalesce(func.avg(Order.carbon_impact), 0.0)).where(Order.status.in_(COUNTED_STATES))
    ))

    eco_orders = db.scalar(
        select(func.count()).select_from(Order)
        .where(Order.delivery_method == "eco", Order.status.in_(COUNTED_STATES))
    ) or 0
    eco_pct = round(100.0 * eco_orders / total_orders, 1) if total_orders else 0.0

    # Units of eco-friendly products sold (join products, filter, SUM quantity).
    eco_units = db.scalar(
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .select_from(OrderItem)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Product.is_eco_friendly.is_(True), Order.status.in_(COUNTED_STATES))
    ) or 0

    # Reduction vs all-Express baseline: for each method, express counterfactual delivery
    # carbon = stored delivery_carbon * (express_factor / method_factor). Aggregate per method
    # (GROUP BY), then apply the constant multiplier in Python (only 3 methods).
    method_co2 = dict(
        db.execute(
            select(Order.delivery_method, func.coalesce(func.sum(Order.delivery_carbon), 0.0))
            .where(Order.status.in_(COUNTED_STATES))
            .group_by(Order.delivery_method)
        ).all()
    )
    saved = 0.0
    for opt in DELIVERY_OPTIONS:
        actual = float(method_co2.get(opt.key, 0.0))
        if actual and opt.emission_factor:
            express_equiv = actual * (_EXPRESS_FACTOR / opt.emission_factor)
            saved += express_equiv - actual

    return SustainabilityReport(
        total_estimated_co2=round(total_co2, 3),
        average_co2_per_order=round(avg_co2, 3),
        eco_delivery_count=eco_orders,
        eco_delivery_percentage=eco_pct,
        eco_products_sold_units=int(eco_units),
        estimated_co2_saved_vs_express=round(saved, 3),
    )
