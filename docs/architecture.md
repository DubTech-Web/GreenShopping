# Architecture

## 1. Style: modular monolith (Spec §4)

One backend process, one database file, one frontend build. No microservices, message
queues, caches, or background workers. Fewer running processes = less idle resource draw,
which is the central green argument (Spec §20, §29).

```
┌─────────────────────────────────────────┐
│  React + Vite + TypeScript (static SPA)   │
│  Pages: Login, Register, Products,        │
│  ProductDetail, Cart, Checkout,           │
│  OrderConfirmation, Admin*                 │
└───────────────────┬───────────────────────┘
                    │ HTTP / JSON  (fetch, no polling)
                    ▼
┌─────────────────────────────────────────┐
│  FastAPI (single ASGI process, uvicorn)   │
│                                            │
│  routers/     auth products cart orders    │
│               recommendations carbon       │
│               delivery admin reports       │
│  services/    security recommender         │
│               carbon delivery inventory    │
│  models.py    SQLAlchemy ORM               │
│  database.py  engine + session             │
└───────────────────┬───────────────────────┘
                    │ SQLAlchemy (parameterized)
                    ▼
┌─────────────────────────────────────────┐
│  SQLite  (single file, WAL mode)          │
│  customers products carts cart_items       │
│  orders order_items recommendation_        │
│  interactions                              │
└─────────────────────────────────────────┘
```

## 2. Backend layering

- **routers/** — thin HTTP layer: validation (Pydantic), auth dependency, status codes.
- **services/** — pure business logic (carbon, delivery, recommender, inventory). No HTTP,
  no I/O where avoidable → unit-testable and reusable, so business rules are never duplicated
  across endpoints (Spec §30).
- **models.py / schemas.py** — ORM tables vs. request/response DTOs kept separate so the API
  never leaks columns the screen doesn't need (Spec §17).

## 3. Request flow example — product detail page (Spec §17 optimized)

`GET /api/products/{id}` → one response containing the product **and** its recommendations
+ eco-alternative, so the detail screen renders from a single round trip instead of three.
See `docs/green-measurements.md` for the naive-vs-optimized comparison.

## 4. Data & transactions

- Order creation runs in **one transaction**: validate stock → create order + items →
  decrement stock → commit. On any failure the whole thing rolls back, so inventory can
  never drift (Spec §9, §26).
- Reports use **SQL aggregation** (`SUM/COUNT/AVG/GROUP BY`) — rows are aggregated in the
  database, never pulled into Python to be summed (Spec §15, §16).

## 5. Auth

Stateless **JWT (HS256)**. The token carries `sub` (customer id) and `is_admin`. No
server-side session store → no Redis/DB session table to run or query (Spec §29). Logout is
a client-side token discard.

## 6. Why not the alternatives (Spec §28)

| Considered | Rejected because |
|---|---|
| PostgreSQL | No concurrency/scale requirement; SQLite is a single file, zero server process. |
| Redis sessions/cache | JWT is stateless; report data is tiny and cheap to aggregate on demand. |
| Celery/queue worker | No long-running or async jobs exist; checkout is fast and synchronous. |
| bcrypt / passlib | stdlib PBKDF2-HMAC-SHA256 is secure and adds no dependency/native build. |
| python-jose[cryptography] | Pulls a heavy Rust build; PyJWT HS256 is pure-Python. |
| A UI component library | Hand-written CSS with design tokens keeps the bundle small. |
