"""Order tests (Spec §9 → Orders: checkout, inventory reduction, order creation)."""
from app.database import get_db
from app.models import Product
from app.services.delivery import estimate_route_distance_km
from tests.conftest import auth_header, register


def _add_product(client, stock=10, price=10.0, weight=0.5, carbon=1.0):
    db = next(client.app.dependency_overrides[get_db]())
    p = Product(name="Widget", description="d", category="A", price=price,
                stock_quantity=stock, weight=weight, eco_score=60, carbon_factor=carbon)
    db.add(p)
    db.commit()
    return p.id


def _cart_with(client, token, pid, qty):
    client.post("/api/cart/items", json={"product_id": pid, "quantity": qty},
                headers=auth_header(token))


def test_checkout_creates_order_and_reduces_inventory(client):
    token = register(client)
    pid = _add_product(client, stock=10, price=10.0)
    _cart_with(client, token, pid, 3)

    resp = client.post("/api/orders",
                       json={"delivery_method": "eco", "delivery_distance": 50},
                       headers=auth_header(token))
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["total_amount"] == 30.0
    assert order["status"] == "Pending Payment"
    assert order["carbon_impact"] > 0

    # Before payment: inventory still 10
    assert client.get(f"/api/products/{pid}").json()["stock_quantity"] == 10

    # Pay & verify
    init = client.post("/api/payments/init", json={"order_id": order["id"]}, headers=auth_header(token)).json()
    paid = client.post("/api/payments/verify", json={"reference": init["reference"]}, headers=auth_header(token)).json()
    assert paid["status"] == "Paid"

    # Inventory reduced 10 -> 7 after payment
    assert client.get(f"/api/products/{pid}").json()["stock_quantity"] == 7
    # Cart emptied after payment
    assert client.get("/api/cart", headers=auth_header(token)).json()["item_count"] == 0


def test_checkout_empty_cart_rejected(client):
    token = register(client)
    resp = client.post("/api/orders",
                       json={"delivery_method": "eco", "delivery_distance": 50},
                       headers=auth_header(token))
    assert resp.status_code == 400


def test_checkout_unknown_delivery_rejected(client):
    token = register(client)
    pid = _add_product(client)
    _cart_with(client, token, pid, 1)
    resp = client.post("/api/orders",
                       json={"delivery_method": "teleport", "delivery_distance": 50},
                       headers=auth_header(token))
    assert resp.status_code == 400


def test_order_appears_in_history(client):
    token = register(client)
    pid = _add_product(client)
    _cart_with(client, token, pid, 1)
    client.post("/api/orders", json={"delivery_method": "standard", "delivery_distance": 20},
                headers=auth_header(token))
    orders = client.get("/api/orders", headers=auth_header(token)).json()
    assert len(orders) == 1
    assert orders[0]["delivery_method"] == "standard"


def test_checkout_calculates_and_stores_route_distance_from_coordinates(client):
    token = register(client)
    pid = _add_product(client)
    _cart_with(client, token, pid, 1)

    resp = client.post(
        "/api/orders",
        json={"delivery_method": "eco", "latitude": 6.5244, "longitude": 3.3792},
        headers=auth_header(token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["delivery_distance"] == estimate_route_distance_km(6.5244, 3.3792)


def test_delivery_destination_requires_both_coordinates(client):
    token = register(client)
    resp = client.post(
        "/api/orders",
        json={"delivery_method": "eco", "latitude": 6.5244},
        headers=auth_header(token),
    )
    assert resp.status_code == 422
