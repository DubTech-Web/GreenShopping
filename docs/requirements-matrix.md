# Requirements-to-Implementation Matrix

This matrix traces **every** functional and green-software requirement to its concrete
implementation. Nothing is built that does not appear here (Spec §2, §35).

Legend: `BE` = backend module, `FE` = frontend page/component, `API` = endpoint(s),
`DB` = tables/columns, `T` = tests.

---

## Functional requirements

### R1 — Customer registration & authentication (Spec §6)
- **Behavior:** Register, log in, log out, access protected customer features.
- **BE:** `routers/auth.py`, `services/security.py` (PBKDF2 hashing + JWT).
- **FE:** `Login.tsx`, `Register.tsx`, `AuthContext`.
- **DB:** `customers(id, name, email, password_hash, is_admin, created_at)`.
- **API:** `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`.
  Logout is client-side token discard (no server session store — see note A).
- **T:** register, login, duplicate email, invalid credentials, protected-route rejection.

### R2 — Product catalog (Spec §7)
- **Behavior:** List products (paginated), view details, filter by category/eco, see
  price, stock status, eco score, carbon info, eco-friendly indicator.
- **BE:** `routers/products.py`.
- **FE:** `Products.tsx`, `ProductDetail.tsx`, `ProductCard.tsx`.
- **DB:** `products(...)`.
- **API:** `GET /api/products?page&limit&category&eco_only&q`, `GET /api/products/{id}`,
  `GET /api/products/meta/categories`.
- **T:** listing, pagination bounds, filtering, detail, 404.

### R3 — Shopping cart (Spec §8)
- **Behavior:** Add, remove, change quantity, view cart, subtotal; block exceeding stock.
- **BE:** `routers/cart.py`.
- **FE:** `Cart.tsx`, `CartContext`.
- **DB:** `carts(id, customer_id)`, `cart_items(id, cart_id, product_id, quantity)`.
- **API:** `GET /api/cart`, `POST /api/cart/items`, `PATCH /api/cart/items/{id}`,
  `DELETE /api/cart/items/{id}`.
- **T:** add, add-over-stock rejected, quantity update, remove, subtotal correctness.

### R4 — Order processing (Spec §9)
- **Behavior:** Cart → checkout → pick delivery → carbon calc → create order → reduce
  inventory → confirmation. Statuses: Pending/Processing/Shipped/Delivered/Cancelled.
- **BE:** `routers/orders.py` (single transaction: create order + items, decrement stock).
- **FE:** `Checkout.tsx`, `OrderConfirmation.tsx`.
- **DB:** `orders(...)`, `order_items(...)`.
- **API:** `POST /api/orders` (simulated checkout), `GET /api/orders`,
  `GET /api/orders/{id}`.
- **T:** checkout creates order, inventory decremented, insufficient-stock rollback.

### R5 — AI recommendation engine (Spec §10, §19)
- **Behavior:** Similar/relevant products for a viewed product; greener alternative with a
  human-readable explanation. Local deterministic weighted scoring — no external LLM.
- **BE:** `services/recommender.py`, `routers/recommendations.py`.
- **FE:** `Recommendations.tsx` (on `ProductDetail`).
- **DB:** reuses `products`; optional `recommendation_interactions` only if history used.
- **API:** `GET /api/products/{id}/recommendations`,
  `GET /api/products/{id}/eco-alternative`.
- **T:** returns same-category items, ranks eco higher, alternative is greener, explanation
  present.

### R6 — Green delivery options (Spec §11)
- **Behavior:** Standard/Eco/Express, each with speed, cost, emission factor; estimate
  emissions; recommend greener (not cheapest) option with reason.
- **BE:** `services/delivery.py` (static option table + calculator).
- **FE:** delivery selector inside `Checkout.tsx`.
- **DB:** none — options are static config (see note B). Chosen method stored on `orders`.
- **API:** `GET /api/delivery/options?distance&weight` (returns options + recommendation).
- **T:** emissions math, eco recommended over express, recommendation ≠ cheapest-only.

### R7 — Carbon footprint estimator (Spec §12)
- **Behavior:** Product carbon + delivery carbon = estimated order carbon (kg CO₂e),
  shown before submit, labelled *estimate*, stored on the order.
- **BE:** `services/carbon.py`.
- **FE:** impact panel in `Checkout.tsx`.
- **DB:** `orders.carbon_impact`, `orders.delivery_distance`, `orders.delivery_method`.
- **API:** `POST /api/carbon/estimate` (preview), and computed server-side at order create.
- **T:** product-carbon sum, delivery-carbon formula, total = products + delivery.

### R8 — Inventory management (Spec §13)
- **Behavior:** Stock levels, updates, reduction after orders, low/out-of-stock indicators,
  threshold-based restock recommendation.
- **BE:** `routers/admin.py` (stock update), `services/inventory.py` (low-stock + restock).
- **FE:** `AdminProducts.tsx`.
- **DB:** `products.stock_quantity`, `products.low_stock_threshold`.
- **API:** `PATCH /api/admin/products/{id}` (stock/fields),
  `GET /api/admin/inventory/restock` (recommendations).
- **T:** stock update, reduction on order, low-stock flag, out-of-stock flag.

### R9 — Administrative dashboard (Spec §14)
- **Behavior:** Manage products/inventory/orders; show sales & sustainability metrics.
- **BE:** `routers/admin.py`, `routers/reports.py`.
- **FE:** `AdminDashboard.tsx`, `AdminProducts.tsx`, `AdminOrders.tsx`.
- **DB:** aggregates over `orders`, `order_items`, `products`.
- **API:** `GET /api/reports/dashboard`, `PATCH /api/admin/orders/{id}` (status).
- **T:** admin-only access enforced; dashboard metric shape.

### R10 — Sales & sustainability reports (Spec §15)
- **Behavior:** Sales (totals, order count, best-sellers, by-category) and sustainability
  (total CO₂, avg per order, eco-delivery %, eco products sold, estimated reduction) via
  **SQL aggregation** (SUM/COUNT/AVG/GROUP BY), rendered as simple charts.
- **BE:** `routers/reports.py`.
- **FE:** `AdminReports.tsx` (Recharts).
- **DB:** aggregate queries only — no analytics tables.
- **API:** `GET /api/reports/sales`, `GET /api/reports/sustainability`.
- **T:** aggregation totals match seeded data; queries use SQL not Python loops.

---

## Green software engineering requirements

### G1 — Eco-friendly delivery recommendations (Spec §11) → satisfied by **R6**.
### G2 — Energy-efficient database operations (Spec §16)
- Indexes on FKs + hot filter columns; pagination everywhere; `SUM/COUNT/AVG/GROUP BY`
  for reports; eager-load to avoid N+1; select only needed columns. Documented & measured.
### G3 — Optimized API calls (Spec §17)
- One request per screen where possible; product detail bundles recommendations client-side
  reuse; no polling; no render-triggered refetch. Measured in `docs/green-measurements.md`.
### G4 — Sustainable hosting considerations (Spec §20) → `docs/green-software.md`.
### G5 — Carbon impact reporting (Spec §21) → satisfied by **R7 + R10** + measurements doc.

---

## Notes & justified deviations from the sample schema

- **Note A — Logout / sessions:** JWT is stateless; logout = client discards token. This
  avoids a server-side session store (Redis/DB) entirely — the greener choice (Spec §17, §29).
- **Note B — Delivery options are static config, not a DB table:** three fixed options with
  fixed factors. A table would add reads + migrations for data that never varies at runtime
  (Spec §5 "if a table is not needed, do not create it").
- **Note C — `is_admin` on `customers`:** the sample schema has no admin concept, but R9 +
  security (§25) require authorization. One boolean is the minimal way to satisfy it.
- **Note D — `low_stock_threshold` on `products`:** required by R8 low-stock detection;
  per-product threshold is more honest than a global constant and costs one small column.
- **Note E — `recommendation_interactions` table:** created **only** because R5 lists
  "customer purchase history" and "products viewed" as inputs. Kept minimal; no other
  analytics are stored (Spec §5).
- **Note F — `orders.delivery_carbon`:** stores the delivery component of an order's carbon
  (the total is also stored). Required so R10's "estimated carbon reduction vs an all-Express
  baseline" (Spec §15) is a clean aggregation instead of reconstructing package weight at
  report time. One float column; consistent with Spec §12 "store the calculated value".
