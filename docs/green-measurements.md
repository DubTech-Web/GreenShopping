# Green Measurements

Measurable green-software indicators (Spec §21, §33), **measured empirically** against the
running app and seed data with `python -m app.measure` (query counting via a SQLAlchemy
`before_cursor_execute` hook; payload sizes from real HTTP responses).

> Reproduce: `cd backend && python -m app.seed && python -m app.measure`

---

## 1. Database queries per operation (measured)

| Operation | Queries | Note |
|---|---:|---|
| Catalog page (12 items) | **2** | 1 `COUNT` + 1 paged `SELECT` — never the whole table. |
| Product detail + recommendations + eco-alt | **4** | auth lookup + product + same-category pool + purchased-ids — all in **one API request**. |
| View cart (any number of items) | **2** | `selectinload` items+products → constant, not `1 + M` (N+1 avoided). |
| Admin dashboard (6 metrics) | **3** | 2 conditional-aggregate `SELECT`s (+1 txn) — folded from 7. |
| Sales report | **5** | `SUM/COUNT` + best-sellers `GROUP BY` + category `GROUP BY`. |
| Sustainability report | **7** | `SUM/AVG/COUNT` + eco-units join + per-method `GROUP BY`. |

The cart figure is the key N+1 result: a naive implementation issues `1 + M` queries (one per
line item); GreenShopping issues **2** whether the cart has 1 item or 50.

### Optimization applied this phase — dashboard 7 → 3 queries
The dashboard originally issued one aggregate per metric (6 `SELECT`s + txn = 7). Folding the
order metrics into a single row with conditional aggregates
(`SUM(CASE WHEN delivery_method='eco' …)`) and the product metrics into another cut it to
**2 `SELECT`s (3 statements incl. the transaction)** — same result, less than half the queries.

## 2. API requests per major workflow (measured / by design)

| Workflow | Naive | GreenShopping | How |
|---|---:|---:|---|
| View product detail + recommendations | 3 | **1** | Detail endpoint bundles recs + eco-alt. |
| Switch delivery method at checkout | 1 per switch | **0** | One `estimate` call returns all options; switching is client-side. |
| Admin dashboard load | 6+ | **1** | Single `/reports/dashboard` aggregate endpoint. |
| Catalog browse (per page) | 1 + N | **1** | Paginated list; shared/compressed assets. |

## 3. Response payload sizes (measured)

| Response | Size |
|---|---:|
| Catalog page (12 product summaries) | 1.65 KB |
| Product detail (full + 4 recs + eco-alt) | 1.07 KB |
| Cart | 0.04 KB |

List rows use a compact `ProductSummary` DTO (no description/carbon fields); those arrive only
on the detail endpoint (Spec §17).

### Pagination payload win (measured)
| Approach | Payload |
|---|---:|
| All 24 products in one response | 3.24 KB |
| One page of 12 | **1.65 KB (49% smaller)** |

With a production-sized catalog the gap widens linearly — the naive "load everything" grows
unbounded while the page stays flat.

## 4. Frontend bundle (measured, `npm run build`)

| Chunk | gzip | Shipped to |
|---|---:|---|
| Customer app (`index`) | **96 KB** | everyone |
| `AdminReports` (Recharts) | 108 KB | admins only, lazy-loaded |
| `AdminDashboard` / `Products` / `Orders` | <1 KB each | admins only, lazy-loaded |

Recharts — the single largest dependency — is code-split into the admin reports route, so the
customer bundle excludes it entirely (Spec §18).

## 5. Unnecessary requests avoided

- No polling anywhere; dashboards do not auto-refresh.
- Categories and delivery options fetched once and reused client-side.
- Cart count refreshes only after a mutation, never on a timer.
- No render-triggered refetch loops (effects keyed to real inputs, guarded with an `active` flag).

## 6. Sustainability outcome metrics (measured from seed data)

From `/api/reports/*` on the seed dataset (6 orders):

| Metric | Value |
|---|---:|
| Total estimated CO₂ | ~28.2 kg CO₂e |
| Average CO₂ per order | ~4.7 kg CO₂e |
| Eco-delivery adoption | 50% |
| Eco-friendly units sold | 15 |
| Estimated CO₂ saved vs all-Express baseline | ~1.6 kg CO₂e |

## 7. Architecture footprint

| Resource | Count | Note |
|---|---:|---|
| Backend processes | 1 | Single FastAPI/uvicorn. |
| Database servers | 0 | SQLite is an in-process file. |
| External services | 0 | No third-party APIs at runtime; recommender is local. |
| Caches / queues / workers | 0 | None required. |
| Backend runtime dependencies | 6 | fastapi, uvicorn, sqlalchemy, pydantic(+settings), PyJWT. |
