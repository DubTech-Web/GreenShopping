# GreenShopping 🌱

**An AI-Powered Sustainable E-Commerce Platform — a demonstration of Green Software Engineering.**

GreenShopping is a deliberately small e-commerce application. It sells products, recommends
greener alternatives, estimates the carbon footprint of each order, and recommends
lower-emission delivery — while the *software itself* is engineered to consume as few
computational, network, storage, and infrastructure resources as reasonably possible.

> The goal is **not** the biggest e-commerce app. The goal is to show how a genuinely useful
> app can be built while minimizing unnecessary compute, network, storage, DB and
> infrastructure — and to **measure** that. (Spec §35)

---

## 1. Project purpose

Academic demonstration of Green Software Engineering: efficiency treated as a first-class
requirement, with sustainability made **measurable**, not merely claimed.

## 2. Requirements

Ten functional requirements (auth, catalog, cart, orders, AI recommendations, green
delivery, carbon estimator, inventory, admin dashboard, reports) and five green requirements
(eco-delivery recommendation, efficient DB ops, optimized API calls, sustainable hosting,
carbon reporting). Every one is traced to code in
[`docs/requirements-matrix.md`](docs/requirements-matrix.md).

## 3. Architecture

Modular monolith: React SPA → FastAPI (single process) → SQLite (single file). No
microservices, queues, caches, or workers. See [`docs/architecture.md`](docs/architecture.md).

## 4. Technology choices

| Layer | Choice | Why (short) |
|---|---|---|
| Frontend | React + Vite + TypeScript | Fast builds, small bundle, typed. No heavy UI kit. |
| Styling | Hand-written CSS + design tokens | Tiny footprint; "Earth & Sky" palette. |
| Backend | FastAPI + Uvicorn | Lightweight, fast, native Python for the recommender. |
| ORM | SQLAlchemy 2.0 | Parameterized queries, eager-loading to avoid N+1. |
| Database | SQLite (WAL) | Single file, **no separate DB server process**. |
| Auth | PyJWT (HS256) + stdlib PBKDF2 | Stateless; **no native build, no extra services**. |
| Recommender | Local weighted scoring | Deterministic, explainable, **no external LLM**. |
| Charts | Recharts | Only dependency added for the required reports. |

Full justifications (incl. why the heavier alternative was avoided) in
[`docs/architecture.md`](docs/architecture.md) §6 and the green docs.

## 5. Database design

Seven tables, created only where a requirement needs them:
`customers, products, carts, cart_items, orders, order_items, recommendation_interactions`.
Schema and justified deviations from the spec's sample schema: `docs/requirements-matrix.md`.

## 6. AI recommendation approach

A **local, deterministic weighted-scoring** algorithm — no external AI API (Spec §10, §19):

```
score = 0.40 · relevance      (same category / attribute overlap)
      + 0.30 · category_similarity
      + 0.30 · sustainability  (eco_score, lower carbon)
```

Every recommendation ships with a plain-language explanation. Documented in
`docs/green-software.md`.

## 7. Carbon calculation approach

```
order_carbon (kg CO₂e) = Σ(product.carbon_factor · qty)         ← products
                       + distance · package_weight · emission_factor  ← delivery
```

All values are clearly labelled **estimates**; the total is stored on the order for
reporting. Assumptions documented in `docs/green-software.md`.

## 8. Green software engineering techniques

Pagination, SQL aggregation, indexes, N+1 avoidance, single-round-trip screens, no polling,
no render-triggered refetch, stateless auth, one process, one DB file. Measured in
[`docs/green-measurements.md`](docs/green-measurements.md).

## 9. API structure

REST under `/api`. Interactive docs at `/docs` when the server runs. Endpoint list in the
requirements matrix.

## 10. How to run

### Backend
```bash
cd backend
python -m venv .venv
# Windows:            .venv\Scripts\activate
# macOS/Linux:        source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed          # create + seed the SQLite database
uvicorn app.main:app --reload
# API:  http://127.0.0.1:8000     docs: http://127.0.0.1:8000/docs
# Seeded admin login:  admin@example.com / adminpass123
# Seeded customer:     ada@example.com   / password123
```

### Frontend
```bash
cd frontend
npm install
npm run dev                  # http://127.0.0.1:5173
```

> Verified toolchain: Python 3.14, Node 24. All backend deps install as prebuilt wheels
> (no C/Rust compiler required).

## 11. How to run tests

```bash
cd backend
pytest -q
```

## 12. Performance / efficiency measurements

See [`docs/green-measurements.md`](docs/green-measurements.md) — **measured** request counts,
query counts, and payload sizes per workflow, plus the naive-vs-optimized comparisons. The
final [`docs/green-audit.md`](docs/green-audit.md) summarizes the whole green engineering story.

## 13. Sustainable hosting considerations

Single small container (or a single Python process) + a static frontend bundle on a CDN;
SQLite needs no DB server. Details in `docs/green-software.md`.

## 14. Limitations

- Carbon numbers are transparent **estimates** with documented factors, not audited LCA data.
- Simulated checkout (no real payment) — by design (Spec §9).
- SQLite suits a single-node demo; a high-concurrency deployment would revisit this.

## 15. Future improvements (NOT implemented — Spec §27)

Optional ML recommender, real payment gateway, live carrier distance/emission APIs. These
are explicitly out of scope for this version.

---

## Project status

All requirements (R1–R10, G1–G5) are implemented, traced, tested, and measured. The build was
done incrementally per the spec's phases; each phase was verified (app runs + tests pass)
before the next. Summary of what's included:

- **Backend:** FastAPI app, 7 SQLAlchemy models, auth, products, cart, orders, carbon,
  delivery, recommender, inventory, admin, reports; seed data; **48 passing tests** incl. a
  full §32 end-to-end acceptance test.
- **Frontend:** React + Vite + TS SPA (Earth & Sky theme) — all required customer and admin
  pages; production build passes with zero type errors; Recharts code-split to admins only.
- **Docs:** requirements matrix, architecture, green-software methodology, measured green
  metrics, API reference, and the final green audit.

### Run everything from scratch
```bash
# Backend (terminal 1)
cd backend && python -m venv .venv && . .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements.txt && python -m app.seed && uvicorn app.main:app --reload
# Frontend (terminal 2)
cd frontend && npm install && npm run dev
# Tests + measurements
cd backend && pytest -q && python -m app.measure
```
