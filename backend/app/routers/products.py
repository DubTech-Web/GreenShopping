"""Product catalog endpoints (Spec §7, R2).

Pagination is mandatory — the full table is never loaded (Spec §7, §16). List responses use
the compact ProductSummary DTO; the full description/carbon fields are only sent by the
detail endpoint (Spec §17 payload minimization).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_optional_customer
from ..models import Customer, Order, OrderItem, Product
from ..schemas import (
    PageMeta,
    ProductDetailWithRecs,
    ProductPage,
    ProductSummary,
    RecommendationItem,
)
from ..services import recommender
from ..services.recommender import ScoredProduct

settings = get_settings()
router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=ProductPage)
def list_products(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size),
    category: str | None = Query(None),
    eco_only: bool = Query(False),
    q: str | None = Query(None, max_length=100),
) -> ProductPage:
    """Paginated, filterable catalog. One COUNT + one paged SELECT (no full-table load)."""
    filters = []
    if category:
        filters.append(Product.category == category)
    if eco_only:
        filters.append(Product.is_eco_friendly.is_(True))
    if q:
        filters.append(Product.name.ilike(f"%{q}%"))

    total = db.scalar(select(func.count()).select_from(Product).where(*filters)) or 0

    rows = db.scalars(
        select(Product)
        .where(*filters)
        .order_by(Product.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    pages = (total + limit - 1) // limit
    return ProductPage(
        items=[ProductSummary.model_validate(p) for p in rows],
        meta=PageMeta(page=page, limit=limit, total=total, pages=pages),
    )


@router.get("/meta/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)) -> list[str]:
    """Distinct categories for the filter UI — fetched once and cached client-side (§17)."""
    return list(db.scalars(select(Product.category).distinct().order_by(Product.category)).all())


def _to_item(scored: ScoredProduct) -> RecommendationItem:
    p = scored.product
    return RecommendationItem(
        id=p.id, name=p.name, image_url=p.image_url, category=p.category, price=float(p.price),
        eco_score=p.eco_score, is_eco_friendly=p.is_eco_friendly,
        carbon_factor=p.carbon_factor, score=scored.score, reason=scored.reason,
    )


@router.get("/{product_id}", response_model=ProductDetailWithRecs)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    customer: Customer | None = Depends(get_optional_customer),
) -> ProductDetailWithRecs:
    """Product detail bundled with recommendations + a greener alternative (Spec §17).

    Queries: 1 (product) + 1 (same-category candidate pool, indexed) [+ 1 purchased-ids if
    signed in]. The whole product page is a single API request.
    """
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # Candidate pool: same category (indexed), capped — not a full-table scan (Spec §16, §21).
    candidates = list(
        db.scalars(
            select(Product)
            .where(Product.category == product.category, Product.id != product.id)
            .limit(50)
        ).all()
    )

    # Purchase history (Spec §10): don't re-recommend what this customer already bought.
    exclude_ids: set[int] = set()
    if customer is not None:
        exclude_ids = set(
            db.scalars(
                select(OrderItem.product_id)
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.customer_id == customer.id)
            ).all()
        )

    similar = recommender.recommend_similar(product, candidates, limit=4, exclude_ids=exclude_ids)
    eco_alt = recommender.find_eco_alternative(product, candidates)

    return ProductDetailWithRecs(
        id=product.id, name=product.name, image_url=product.image_url, category=product.category, price=float(product.price),
        stock_quantity=product.stock_quantity, eco_score=product.eco_score,
        is_eco_friendly=product.is_eco_friendly, description=product.description,
        weight=product.weight, carbon_factor=product.carbon_factor,
        low_stock_threshold=product.low_stock_threshold,
        recommendations=[_to_item(s) for s in similar],
        eco_alternative=_to_item(eco_alt) if eco_alt else None,
    )
