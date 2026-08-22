"""Cart tests (Spec §9 → Cart: add, remove, quantity updates; stock guard §8)."""
from app.database import get_db
from app.models import Product
from tests.conftest import auth_header, register


def _add_product(client, stock=5, price=10.0):
    db = next(client.app.dependency_overrides[get_db]())
    p = Product(name="Widget", description="d", category="A", price=price,
                stock_quantity=stock, weight=0.5, eco_score=60, carbon_factor=1.0)
    db.add(p)
    db.commit()
    return p.id


def test_add_and_view_cart(client):
    token = register(client)
    pid = _add_product(client, stock=5, price=10.0)
    resp = client.post("/api/cart/items", json={"product_id": pid, "quantity": 2},
                       headers=auth_header(token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["item_count"] == 2
    assert body["subtotal"] == 20.0


def test_add_over_stock_rejected(client):
    token = register(client)
    pid = _add_product(client, stock=3)
    resp = client.post("/api/cart/items", json={"product_id": pid, "quantity": 4},
                       headers=auth_header(token))
    assert resp.status_code == 409


def test_update_quantity(client):
    token = register(client)
    pid = _add_product(client, stock=10)
    client.post("/api/cart/items", json={"product_id": pid, "quantity": 1},
                headers=auth_header(token))
    item_id = client.get("/api/cart", headers=auth_header(token)).json()["items"][0]["id"]
    resp = client.patch(f"/api/cart/items/{item_id}", json={"quantity": 5},
                        headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["item_count"] == 5


def test_remove_item(client):
    token = register(client)
    pid = _add_product(client)
    client.post("/api/cart/items", json={"product_id": pid, "quantity": 1},
                headers=auth_header(token))
    item_id = client.get("/api/cart", headers=auth_header(token)).json()["items"][0]["id"]
    resp = client.delete(f"/api/cart/items/{item_id}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["item_count"] == 0


def test_cart_requires_auth(client):
    assert client.get("/api/cart").status_code == 401
