# Green Software Engineering

This is the central academic purpose of GreenShopping (Spec §16, §35). Sustainable software
is not only the user-visible "green" features — **the software itself consumes fewer
resources**. This document records the methodology; measured results live in
[`green-measurements.md`](green-measurements.md).

---

## 1. Efficient database operations (Spec §16, G2)

- **Indexes** on foreign keys and hot filter columns (`products.category`,
  `products.is_eco_friendly`, `orders.customer_id`, `orders.created_at`).
- **Pagination** on every list endpoint — never `SELECT *` across the whole table.
- **SQL aggregation** (`SUM/COUNT/AVG/GROUP BY`) for all reports; rows are never pulled into
  Python just to be totalled.
- **N+1 avoidance** via SQLAlchemy eager loading (`selectinload`) on cart/order item reads.
- **No polling, no unnecessary writes**, no analytics rows beyond what R5 needs.

## 2. Optimized API calls (Spec §17, G3)

- One request per screen where feasible (product detail bundles its recommendations).
- Responses carry only fields the screen needs (DTOs ≠ ORM rows).
- Client caches static data (categories, delivery options) instead of refetching.
- No render-triggered refetch loops; no auto-refresh dashboards.

## 3. AI resource efficiency (Spec §19)

The recommender is a **local deterministic weighted-scoring** function — no external LLM,
no per-view network call. Similarity, carbon, delivery, inventory thresholds, and reports
are all plain algorithms. AI never becomes the largest resource consumer.

### Recommendation algorithm (explainable)
```
score(candidate | seed) =
    0.40 · relevance            # attribute/keyword overlap with the seed product
  + 0.30 · category_similarity  # 1.0 same category, else partial
  + 0.30 · sustainability       # normalized eco_score, bonus for lower carbon_factor
```
Eco-alternative = highest-scoring candidate in the same category with a **higher eco_score
and lower carbon_factor** than the seed. Each result includes a generated reason string.

## 4. Carbon estimation methodology (Spec §12, §21, G5)

```
product_carbon  = Σ (product.carbon_factor[kg CO₂e/unit] · quantity)
delivery_carbon = distance[km] · package_weight[kg] · method.emission_factor[kg CO₂e/kg·km]
order_carbon    = product_carbon + delivery_carbon
```
All figures are **estimates** with documented factors (see below), shown before checkout and
stored on the order for reporting. No claims of exact real-world emissions are made.

Checkout requests the customer's location through the browser only after they select **Use my
current location**. The server calculates straight-line distance from the representative
Abuja dispatch point (9.05785, 7.49508) and applies a 1.3 road-distance allowance as a rough
route estimate. It does not query a maps provider, so the coordinates are not shared with a
third party; they are not stored on the order. Only the estimated route kilometres and carbon
estimate are retained. This allowance is not a substitute for carrier route data and can vary
from the actual road route.

## 5. Green delivery methodology (Spec §11, G1)

Three static options (no DB table needed):

| Method | Speed | Cost | Emission factor (kg CO₂e/kg·km) |
|---|---|---|---|
| Eco | Slowest | Low | lowest |
| Standard | Medium | Medium | medium |
| Express | Fastest | Highest | highest |

The system recommends the option with the **lowest estimated carbon impact**, with a reason
— explicitly *not* simply the cheapest.

## 6. Sustainable hosting considerations (Spec §20, G4)

- **Low resource consumption:** one ASGI process, one SQLite file — no DB server, cache, or
  worker to keep running and drawing power at idle.
- **Lightweight container:** a slim Python base image; the frontend is static files served by
  a CDN/static host (near-zero origin compute).
- **Appropriate scaling, not overprovisioning:** the demo runs comfortably on the smallest
  instance tier; scale only if real load demands it.
- **Optimized static assets:** Vite production build (minified, tree-shaken, hashed);
  product images compressed/resized.

## 7. Emission & eco-score assumptions (transparency)

- `carbon_factor` is a per-unit estimate (kg CO₂e) attached to each product in seed data.
- `eco_score` is a 0–100 sustainability rating used for ranking and reporting.
- Delivery emission factors are relative, documented constants in `services/delivery.py`.
- These are illustrative academic estimates, not audited life-cycle assessment figures.
