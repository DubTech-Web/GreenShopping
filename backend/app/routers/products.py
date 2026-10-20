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
from ..deps import get_current_customer, get_optional_customer
from ..models import Customer, Order, OrderItem, Product, ProductRating
from ..schemas import (
    PageMeta,
    ProductDetailWithRecs,
    ProductPage,
    ProductRatingRequest,
    ProductRatingSummary,
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
    ratings = _rating_stats(db, [product.id for product in rows])

    pages = (total + limit - 1) // limit
    return ProductPage(
        items=[
            ProductSummary.model_validate(p).model_copy(
                update={
                    "rating_average": ratings.get(p.id, (0.0, 0))[0],
                    "rating_count": ratings.get(p.id, (0.0, 0))[1],
                }
            )
            for p in rows
        ],
        meta=PageMeta(page=page, limit=limit, total=total, pages=pages),
    )


@router.get("/meta/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)) -> list[str]:
    """Distinct categories for the filter UI — fetched once and cached client-side (§17)."""
    return list(db.scalars(select(Product.category).distinct().order_by(Product.category)).all())


def _to_item(
    scored: ScoredProduct, rating_stats: tuple[float, int] = (0.0, 0)
) -> RecommendationItem:
    p = scored.product
    return RecommendationItem(
        id=p.id, name=p.name, image_url=p.image_url, category=p.category, price=float(p.price),
        eco_score=p.eco_score, is_eco_friendly=p.is_eco_friendly,
        rating_average=rating_stats[0], rating_count=rating_stats[1],
        carbon_factor=p.carbon_factor, score=scored.score, reason=scored.reason,
    )


def _rating_stats(db: Session, product_ids: list[int]) -> dict[int, tuple[float, int]]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(
            ProductRating.product_id,
            func.avg(ProductRating.rating),
            func.count(ProductRating.id),
        )
        .where(ProductRating.product_id.in_(product_ids))
        .group_by(ProductRating.product_id)
    ).all()
    return {int(product_id): (float(average), int(count)) for product_id, average, count in rows}


@router.get("/{product_id}", response_model=ProductDetailWithRecs)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    customer: Customer | None = Depends(get_optional_customer),
) -> ProductDetailWithRecs:
    """Product detail bundled with recommendations + a greener alternative (Spec §17).

    Queries: 1 (product) + 1 (same-category candidate pool, indexed), with batched ratings
    and optional customer history. The whole product page is a single API request.
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
    ratings = _rating_stats(db, [product.id, *(candidate.id for candidate in candidates)])

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
        user_rating = db.scalar(
            select(ProductRating.rating).where(
                ProductRating.product_id == product.id,
                ProductRating.customer_id == customer.id,
            )
        )
    else:
        user_rating = None

    similar = recommender.recommend_similar(
        product,
        candidates,
        limit=4,
        exclude_ids=exclude_ids,
        rating_scores={product_id: average for product_id, (average, _) in ratings.items()},
    )
    eco_alt = recommender.find_eco_alternative(product, candidates)
    rating_average, rating_count = ratings.get(product.id, (0.0, 0))

    return ProductDetailWithRecs(
        id=product.id, name=product.name, image_url=product.image_url, category=product.category, price=float(product.price),
        stock_quantity=product.stock_quantity, eco_score=product.eco_score,
        is_eco_friendly=product.is_eco_friendly, description=product.description,
        weight=product.weight, carbon_factor=product.carbon_factor,
        low_stock_threshold=product.low_stock_threshold,
        rating_average=rating_average, rating_count=rating_count, user_rating=user_rating,
        recommendations=[_to_item(s, ratings.get(s.product.id, (0.0, 0))) for s in similar],
        eco_alternative=(
            _to_item(eco_alt, ratings.get(eco_alt.product.id, (0.0, 0))) if eco_alt else None
        ),
    )


@router.post("/{product_id}/rating", response_model=ProductRatingSummary)
def rate_product(
    product_id: int,
    payload: ProductRatingRequest,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
) -> ProductRatingSummary:
    """Create or replace this customer's 1–5 star rating for a product."""
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    rating = db.scalar(
        select(ProductRating).where(
            ProductRating.product_id == product_id,
            ProductRating.customer_id == customer.id,
        )
    )
    if rating is None:
        rating = ProductRating(
            customer_id=customer.id,
            product_id=product_id,
            rating=payload.rating,
        )
        db.add(rating)
    else:
        rating.rating = payload.rating

    db.commit()
    average, count = _rating_stats(db, [product_id]).get(product_id, (0.0, 0))
    return ProductRatingSummary(
        rating_average=average,
        rating_count=count,
        user_rating=payload.rating,
    )
