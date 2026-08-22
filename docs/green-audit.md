# Final Green Software Engineering Audit

Per Spec §33. All figures are measured against the running app and seed data
(`python -m app.measure`, `pytest`) or read from the production build.

---

## Architecture

| Item | Count | Why necessary |
|---|---:|---|
| Backend services | **1** | Single FastAPI/uvicorn process — modular monolith (Spec §4). |
| Database services | **0** | SQLite is in-process (a file); no DB server to run or power. |
| External runtime services | **0** | Recommender is local; no third-party API on any request path. |
| Caches / queues / workers | **0** | Stateless JWT, synchronous checkout, on-demand aggregation — none needed. |

Fewer always-running processes is the core green lever: nothing idles drawing power between
requests.

## Dependencies

| Layer | Major deps | Notes |
|---|---:|---|
| Backend runtime | **5** | fastapi, uvicorn, sqlalchemy, pydantic(+settings), PyJWT. |
| Backend test-only | 2 | pytest, httpx (TestClient). |
| Frontend runtime | **4** | react, react-dom, react-router-dom, recharts. |

Deliberately avoided (Spec §29): Redis, Kafka, RabbitMQ, Kubernetes, Elasticsearch, GraphQL,
WebSockets, external analytics, any AI API, and any UI component framework. Two swaps were
made specifically to remove native builds / weight: **PyJWT** instead of
`python-jose[cryptography]`, and **stdlib PBKDF2** instead of bcrypt/passlib. No unnecessary
dependency was found to remove in the final pass.

## Database

- **Indexes:** FKs plus hot filter/sort columns — `products.category`,
  `products.is_eco_friendly`, `orders.customer_id`, `orders.status`, `orders.created_at`,
  and the cart/order-item FKs.
- **Query optimization:** reports use `SUM/COUNT/AVG/GROUP BY`; the dashboard folds 6 metrics
  into 2 conditional-aggregate queries (**7 → 3** statements incl. txn).
- **Pagination:** every list endpoint; the catalog never loads the whole table.
- **N+1 avoided:** cart and order reads `selectinload` their products — **2 queries for any
  cart size** (vs. naive `1 + M`), measured.

## API

| Workflow | Requests | 
|---|---:|
| View product detail + recommendations + eco-alt | **1** (bundled) |
| Switch delivery method at checkout | **0** (client-side reuse of one estimate) |
| Admin dashboard | **1** aggregate endpoint |

- **Response sizes (measured):** catalog page 1.65 KB, product detail 1.07 KB, cart 0.04 KB.
- List DTOs omit heavy fields (description/carbon) — those ship only on the detail endpoint.
- No polling; no render-triggered refetch.

## Frontend

- **Asset optimization:** Vite production build — minified, tree-shaken, hashed, gzipped.
  No raster product images (lightweight inline SVG/emoji thumbnails) → no image bytes to ship.
- **Bundle (gzip):** customer app **96 KB**; Recharts (**108 KB**) is code-split into the
  admin reports route so customers never download it; other admin routes < 1 KB each.
- **Rendering:** effects keyed to real inputs and guarded against stale updates; cart count
  refreshes on mutation only; hand-written CSS (no runtime CSS-in-JS).

## AI

- **External/AI calls per request:** **0.** The recommender is a local, deterministic
  weighted-scoring function (`0.40 relevance + 0.30 category + 0.30 sustainability`).
- **Caching strategy:** not needed — there is no external call to cache; scoring is cheap and
  runs over an indexed same-category candidate pool.
- **Why deterministic, not AI:** similarity, carbon, delivery, inventory thresholds and reports
  are exact calculations. An LLM would add latency, cost, energy, and nondeterminism for no
  correctness gain (Spec §19). AI is therefore never the largest resource consumer — it draws
  none.

## Sustainability (methodology)

- **Carbon estimation:** `product_carbon = Σ(carbon_factor · qty)`;
  `delivery_carbon = distance · weight · emission_factor`; total stored on the order. All
  labelled estimates (kg CO₂e).
- **Green delivery:** three static options; the system recommends the **lowest-carbon** option
  with a reason — explicitly not the cheapest.
- **Metrics (seed data):** ~28.2 kg CO₂e total; ~4.7 kg/order; 50% eco-delivery adoption; 15
  eco units sold; ~1.6 kg CO₂e estimated saving vs an all-Express baseline.

## Hosting

- **Deployment:** one slim Python container (or a single process) + a static frontend bundle on
  a CDN/static host. SQLite needs no database server.
- **Resource-conscious config:** smallest instance tier suffices; scale only on real demand
  (no overprovisioning); WAL + `synchronous=NORMAL` reduce write overhead; static assets
  hashed and long-cacheable.

---

## Verdict

Every functional (R1–R10) and green (G1–G5) requirement is implemented and traced
(`docs/requirements-matrix.md`), the full §32 acceptance workflow passes end-to-end
(`tests/test_acceptance.py`), and the efficiency claims are backed by measured numbers rather
than assertions. Nothing outside the requirements was built; using fewer resources was an
explicit engineering decision throughout.
