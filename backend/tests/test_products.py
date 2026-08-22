"""Product catalog tests (Spec §9 → Products: retrieval, pagination, details)."""
from app.database import get_db
from app.models import Product


def _seed_products(client, n=25):
    """Insert products directly through the overridden test DB session."""
    db = next(client.app.dependency_overrides[get_db]())
    for i in range(n):
        db.add(
            Product(
                name=f"Product {i:02d}", description="d", category="A" if i % 2 else "B",
                price=1.0 + i, stock_quantity=10, weight=0.5, eco_score=50 + (i % 40),
                carbon_factor=1.0, is_eco_friendly=(i % 3 == 0),
            )
        )
    db.commit()


def test_list_products_paginated(client):
    _seed_products(client, 25)
    resp = client.get("/api/products?page=1&limit=20")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 20
    assert body["meta"]["total"] == 25
    assert body["meta"]["pages"] == 2


def test_pagination_second_page(client):
    _seed_products(client, 25)
    resp = client.get("/api/products?page=2&limit=20")
    assert len(resp.json()["items"]) == 5


def test_filter_eco_only(client):
    _seed_products(client, 25)
    resp = client.get("/api/products?eco_only=true&limit=100")
    items = resp.json()["items"]
    assert items and all(p["is_eco_friendly"] for p in items)


def test_product_detail_and_404(client):
    _seed_products(client, 3)
    assert client.get("/api/products/1").status_code == 200
    assert client.get("/api/products/9999").status_code == 404


def test_summary_excludes_heavy_fields(client):
    """List payload stays compact — no description/carbon_factor (Spec §17)."""
    _seed_products(client, 1)
    item = client.get("/api/products").json()["items"][0]
    assert "description" not in item and "carbon_factor" not in item
