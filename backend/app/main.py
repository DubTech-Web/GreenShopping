"""FastAPI application entrypoint (Spec §4).

A single ASGI app wires the feature routers to one SQLite database. Routers are added
per phase; auth is the foundation established in Phase 2.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, engine
from .routers import admin, auth, cart, carbon, orders, products, reports

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create tables if absent. Seeding is a separate explicit step (python -m app.seed).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="GreenShopping API",
    version="0.1.0",
    summary="AI-powered sustainable e-commerce — Green Software Engineering demo.",
    lifespan=lifespan,
)

# Explicit CORS origins (not '*') so the dev frontend works without weakening security (§25).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(carbon.router)
app.include_router(admin.router)
app.include_router(reports.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
