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

The second-phase checkout uses a backend-authoritative Paystack demonstration charge of
₦100 (`PAYMENT_AMOUNT_KOBO=10000`), independent of the displayed product and cart prices.
With no payment or email provider configured, local development uses offline payment and
verification-code simulation (the code is returned in the API response); once an email
provider (Gmail SMTP or Resend) is set, codes are emailed and never returned to the client,
and production requires both a payment and an email provider.

Product cards use optimized Unsplash photographs (`640px`, quality `75`) with lazy loading;
the primary product-detail image loads eagerly. This keeps the repository small while using
real product imagery instead of inline illustrations.

### Production configuration

Deploy the frontend to Vercel with `VITE_API_URL` set to the Render API URL. Deploy the
backend with the environment variables in [`backend/.env.example`](backend/.env.example),
including a managed PostgreSQL `DATABASE_URL`, a strong `JWT_SECRET`, `FRONTEND_URL`, Resend
credentials, and Paystack credentials. [`render.yaml`](render.yaml) contains the minimal
Render web-service definition. The backend creates the schema on startup; run
`python -m app.seed` once against a fresh managed database when sample data is needed.

Email setup (verification codes + order receipts): the backend tries **SMTP first, then
Resend**, and falls back to a dev code (surfaced in the API response, non-production only) when
neither is set. The recommended free option that delivers to **any** recipient with no custom
domain is **Gmail SMTP with an App Password**: enable 2-Step Verification on the Google
account, create an App Password, then set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`,
`SMTP_USER`, `SMTP_PASSWORD` (the App Password), and `SMTP_FROM_EMAIL`. Resend is an optional
alternative, but its free tier only delivers to the account owner unless a custom domain is
verified. Paystack setup: create test/live keys, set the secret and public keys on the backend,
and keep the fixed `PAYMENT_AMOUNT_KOBO=10000` value unchanged for this assignment.

### Migrating SQLite to PostgreSQL

Provision a managed PostgreSQL database with Neon, Supabase, or Render PostgreSQL and copy
its connection string into `backend/.env` as `DATABASE_URL`. From the `backend` directory,
run:

```bash
# Windows PowerShell
$env:DATABASE_URL="postgresql://user:password@host/database"
python -m app.migrate_database
```

The migration creates the current SQLAlchemy schema, copies rows from the local
`greenshopping.db` (or `SOURCE_DATABASE_URL`), preserves existing IDs, and resets PostgreSQL
sequences. It copies only columns shared by both schemas, so new second-phase columns receive
their model defaults. Review the target database before running it and take a backup first;
the script does not delete target data and will fail on duplicate rows. To initialize a fresh
managed database instead, set `DATABASE_URL` and run `python -m app.seed`.

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
