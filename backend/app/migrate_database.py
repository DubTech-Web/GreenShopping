"""Copy the local SQLite database into a configured PostgreSQL database.

Usage from backend/:
    DATABASE_URL=postgresql://... python -m app.migrate_database

The target schema is created from the current SQLAlchemy models. Only columns present in
both databases are copied, allowing newly added second-phase columns to use model defaults.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, inspect, text

from .database import Base, _normalize_url
from .config import get_settings
from . import models  # noqa: F401  # register all tables with Base.metadata
from .seed import IMAGE_URLS


def migrate() -> None:
    source_url = os.getenv("SOURCE_DATABASE_URL", "sqlite:///./greenshopping.db")
    target_url = _normalize_url(get_settings().database_url)
    if target_url.startswith("sqlite"):
        raise RuntimeError("DATABASE_URL must point to PostgreSQL for this migration")

    source = create_engine(source_url)
    target = create_engine(target_url, pool_pre_ping=True)
    Base.metadata.create_all(target)

    with source.connect() as source_connection, target.begin() as target_connection:
        source_tables = set(source_connection.dialect.get_table_names(source_connection))
        source_inspector = inspect(source_connection)
        for table in Base.metadata.sorted_tables:
            if table.name not in source_tables:
                continue
            source_columns = {column["name"] for column in source_inspector.get_columns(table.name)}
            target_columns = {column.name for column in table.columns}
            columns = [column.name for column in table.columns if column.name in source_columns & target_columns]
            if not columns:
                continue
            rows = source_connection.execute(table.select().with_only_columns(*[table.c[name] for name in columns])).mappings()
            values = [dict(row) for row in rows]
            if values:
                target_connection.execute(table.insert().values(values))

        for name, image_url in IMAGE_URLS.items():
            target_connection.execute(
                text("UPDATE products SET image_url = :image_url WHERE name = :name"),
                {"name": name, "image_url": image_url},
            )

        for table in Base.metadata.sorted_tables:
            if "id" not in table.c:
                continue
            target_connection.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table.name}), 1), "
                f"(SELECT MAX(id) IS NOT NULL FROM {table.name}))"
            ))

    print("PostgreSQL migration completed.")


if __name__ == "__main__":
    migrate()
