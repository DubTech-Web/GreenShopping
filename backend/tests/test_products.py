"""Product catalog tests (Spec §9 → Products: retrieval, pagination, details)."""
from app.database import get_db
from app.models import Product
from tests.conftest import auth_header, register


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


def test_product_ratings_are_saved_and_aggregated(client):
    _seed_products(client, 1)
    token = register(client, email="rating-user@example.com")
    product_id = 1

    assert client.post(f"/api/products/{product_id}/rating", json={"rating": 5},
                       headers=auth_header(token)).status_code == 200
    detail = client.get(f"/api/products/{product_id}", headers=auth_header(token)).json()
    assert detail["rating_average"] == 5
    assert detail["rating_count"] == 1
    assert detail["user_rating"] == 5

    # A customer's next rating replaces their previous one rather than adding a duplicate.
    response = client.post(f"/api/products/{product_id}/rating", json={"rating": 3},
                           headers=auth_header(token))
    assert response.status_code == 200
    assert response.json() == {"rating_average": 3, "rating_count": 1, "user_rating": 3}
    assert client.get("/api/products").json()["items"][0]["rating_average"] == 3


def test_product_ratings_require_auth_and_validate_stars(client):
    _seed_products(client, 1)
    assert client.post("/api/products/1/rating", json={"rating": 5}).status_code == 401

    token = register(client, email="rating-validation@example.com")
    response = client.post("/api/products/1/rating", json={"rating": 6},
                           headers=auth_header(token))
    assert response.status_code == 422
