"""Database engine and session management (Spec §3, §16; Phase-2 §16–§18).

Local development uses SQLite (a single file, no separate server). Production uses a managed
PostgreSQL instance via `DATABASE_URL` (Spec Phase-2 §16). The same SQLAlchemy models and
business logic run on both — only the engine setup differs here.

Efficiency choices carried over from the SQLite design (Spec §16): one session per request,
no autoflush surprises, connection pre-ping so a dropped managed-Postgres connection is
transparently replaced rather than erroring a request.
"""
from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()


def _normalize_url(url: str) -> str:
    """Accept the `postgres://` scheme some hosts emit and give SQLAlchemy a real driver.

    Neon/Render/Supabase commonly hand out `postgres://...`; SQLAlchemy needs an explicit
    dialect+driver. We standardise on psycopg (v3), which installs as a prebuilt wheel.
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


_url = _normalize_url(settings.database_url)
_is_sqlite = _url.startswith("sqlite")

if settings.is_production and _is_sqlite:
    raise RuntimeError("Production requires a managed PostgreSQL DATABASE_URL")

# SQLite: allow cross-thread use of the single connection. Postgres: pre-ping so idle
# connections dropped by the managed host are replaced rather than surfaced as errors.
if _is_sqlite:
    engine = create_engine(_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(_url, pool_pre_ping=True)


if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        """Enforce FKs and enable WAL — WAL gives cheaper concurrent reads/writes (Spec §16).

        Registered only for SQLite; PostgreSQL enforces FKs natively and has no PRAGMAs.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def upgrade_legacy_sqlite_schema() -> None:
    if not _is_sqlite:
        return
    inspector = inspect(engine)
    with engine.begin() as connection:
        upgrades = {
            "customers": {"is_verified": "BOOLEAN NOT NULL DEFAULT 1"},
            "orders": {
                "stock_deducted": "BOOLEAN NOT NULL DEFAULT 1",
                "payment_reference": "VARCHAR(100)",
            },
            "products": {"image_url": "VARCHAR(500) NOT NULL DEFAULT ''"},
        }
        for table, columns in upgrades.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for column, definition in columns.items():
                if column not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed (no leaked connections)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
