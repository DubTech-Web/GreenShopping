"""Add and populate product image URLs in an existing database.

Run from backend/ after setting DATABASE_URL:
    python -m app.backfill_product_images
"""
from sqlalchemy import inspect, text

from .database import engine
from .seed import IMAGE_URLS


def backfill() -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("products")}
    with engine.begin() as connection:
        if "image_url" not in columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN image_url VARCHAR(500) NOT NULL DEFAULT ''"))
        for name, image_url in IMAGE_URLS.items():
            connection.execute(
                text("UPDATE products SET image_url = :image_url WHERE name = :name"),
                {"name": name, "image_url": image_url},
            )
    print(f"Updated {len(IMAGE_URLS)} product image URLs.")


if __name__ == "__main__":
    backfill()
