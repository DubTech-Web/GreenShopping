# API Documentation

Base URL: `http://127.0.0.1:8000` · All app endpoints are under `/api`. Interactive docs are
served at `/docs` (Swagger UI) and `/redoc` when the server runs. Auth is a Bearer JWT in the
`Authorization` header.

Access levels: **Public** (no token) · **Customer** (valid token) · **Admin** (token with
`is_admin`). Errors use standard HTTP codes with `{ "detail": "message" }` (Spec §26).

---

## Auth (R1)
| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | Public | Create account; returns a JWT. |
| POST | `/api/auth/login` | Public | Exchange email+password for a JWT. |
| GET | `/api/auth/me` | Customer | Current user profile. |

Logout is client-side (discard the token) — the JWT is stateless, so there is no server
session to end (matrix Note A).

## Products (R2) + Recommendations (R5)
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/products?page&limit&category&eco_only&q` | Public | Paginated, filterable catalog (compact summaries). |
| GET | `/api/products/meta/categories` | Public | Distinct categories (fetch once, cache client-side). |
| GET | `/api/products/{id}` | Public (optional auth) | Product detail **bundled** with `recommendations` + `eco_alternative`. Auth ⇒ excludes already-purchased items. |

## Cart (R3)
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/cart` | Customer | Cart with items + subtotal. |
| POST | `/api/cart/items` | Customer | Add item (rejects exceeding stock). |
| PATCH | `/api/cart/items/{id}` | Customer | Change quantity (stock-checked). |
| DELETE | `/api/cart/items/{id}` | Customer | Remove item. |

## Carbon estimator (R7) + Green delivery (R6)
| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/api/carbon/estimate` | Customer | For the current cart + a distance: product carbon, every delivery option's carbon + total, and the recommended greener option. One call powers the checkout impact panel. |

## Orders (R4)
| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/api/orders` | Customer | Simulated checkout: validates stock, computes+stores carbon, creates order, reduces inventory (one transaction). |
| GET | `/api/orders` | Customer | Order history (summaries). |
| GET | `/api/orders/{id}` | Customer | Order detail with items. |

## Admin — products, inventory, orders (R8, R9)
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/admin/products?page&limit` | Admin | Products with stock status. |
| POST | `/api/admin/products` | Admin | Create a product. |
| PATCH | `/api/admin/products/{id}` | Admin | Update fields / stock (partial). |
| GET | `/api/admin/inventory/restock` | Admin | Threshold + recent-demand restock suggestions. |
| GET | `/api/admin/orders?page&limit` | Admin | All orders. |
| PATCH | `/api/admin/orders/{id}` | Admin | Update order status. |

## Reports (R9, R10) + Carbon reporting (G5)
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/reports/dashboard` | Admin | 6 headline metrics (2 aggregate queries). |
| GET | `/api/reports/sales` | Admin | Totals, best-sellers, revenue by category. |
| GET | `/api/reports/sustainability` | Admin | Total/avg CO₂, eco-delivery %, eco units sold, saving vs Express. |

## Meta
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/health` | Public | Liveness check. |

---

### Example: bundled product detail (the §17 optimization)
```
GET /api/products/1
→ {
    "id": 1, "name": "Standard Plastic Water Bottle", "price": 4.99, "eco_score": 25, …,
    "recommendations": [ { "id": 2, "name": "Reusable Stainless Steel Bottle",
                           "score": 0.71, "reason": "Recommended because it is same category…" }, … ],
    "eco_alternative":  { "id": 2, "name": "Reusable Stainless Steel Bottle",
                          "reason": "Greener alternative … eco score 90 vs 25 …" }
  }
```
One request returns the product, its similar items, and the greener alternative.
