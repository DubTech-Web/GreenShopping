"""Admin & inventory tests (Spec §9 → Inventory: stock updates, low stock, out of stock;
authorization for admin functionality §25)."""
from app.database import get_db
from app.models import Customer, Product
from app.services import inventory
from app.services.security import hash_password
from tests.conftest import auth_header, register


def _make_admin(client, email="admin@example.com"):
    db = next(client.app.dependency_overrides[get_db]())
    admin = Customer(name="Admin", email=email, password_hash=hash_password("adminpass123"),
                     is_admin=True)
    db.add(admin)
    db.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": "adminpass123"})
    return resp.json()["access_token"]


def _add_product(client, **kw):
    db = next(client.app.dependency_overrides[get_db]())
    base = dict(name="Widget", description="d", category="A", price=10.0, stock_quantity=10,
                weight=0.5, eco_score=60, carbon_factor=1.0, low_stock_threshold=5)
    base.update(kw)
    p = Product(**base)
    db.add(p)
    db.commit()
    return p.id


# ---- Service-level stock status (Spec §13) ----
def test_stock_status_transitions():
    p = Product(name="x", description="", category="A", price=1, stock_quantity=10,
                weight=0.5, eco_score=50, carbon_factor=1.0, low_stock_threshold=5)
    p.stock_quantity = 10
    assert inventory.stock_status(p) == inventory.IN_STOCK
    p.stock_quantity = 5
    assert inventory.stock_status(p) == inventory.LOW_STOCK
    p.stock_quantity = 0
    assert inventory.stock_status(p) == inventory.OUT_OF_STOCK


def test_restock_suggestion_for_low_stock():
    p = Product(name="x", description="", category="A", price=1, stock_quantity=3,
                weight=0.5, eco_score=50, carbon_factor=1.0, low_stock_threshold=5)
    p.id = 1
    s = inventory.restock_suggestion(p, recent_units_sold=2)
    assert s is not None and s.suggested_reorder_qty > 0


def test_no_restock_when_healthy():
    p = Product(name="x", description="", category="A", price=1, stock_quantity=50,
                weight=0.5, eco_score=50, carbon_factor=1.0, low_stock_threshold=5)
    p.id = 1
    assert inventory.restock_suggestion(p, recent_units_sold=1) is None


# ---- Authorization (Spec §25) ----
def test_admin_routes_reject_non_admin(client):
    token = register(client, email="plain@example.com")  # normal customer
    assert client.get("/api/admin/products", headers=auth_header(token)).status_code == 403


def test_admin_routes_reject_anonymous(client):
    assert client.get("/api/admin/products").status_code == 401


# ---- Product management & inventory (Spec §13, §14) ----
def test_admin_update_stock(client):
    token = _make_admin(client)
    pid = _add_product(client, stock_quantity=10)
    resp = client.patch(f"/api/admin/products/{pid}", json={"stock_quantity": 2},
                        headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["stock_quantity"] == 2
    assert body["stock_status"] == "low_stock"


def test_admin_create_product(client):
    token = _make_admin(client)
    resp = client.post("/api/admin/products", headers=auth_header(token), json={
        "name": "New Eco Item", "category": "Home", "price": 9.99, "stock_quantity": 20,
        "weight": 0.4, "eco_score": 85, "carbon_factor": 0.5, "is_eco_friendly": True,
    })
    assert resp.status_code == 201
    assert resp.json()["stock_status"] == "in_stock"


def test_restock_endpoint_flags_low_stock(client):
    token = _make_admin(client)
    _add_product(client, name="Low", stock_quantity=1, low_stock_threshold=5)
    _add_product(client, name="Healthy", stock_quantity=100, low_stock_threshold=5)
    rows = client.get("/api/admin/inventory/restock", headers=auth_header(token)).json()
    names = [r["name"] for r in rows]
    assert "Low" in names and "Healthy" not in names


def test_admin_update_order_status(client):
    token = _make_admin(client)
    # Create an order as a customer first.
    cust = register(client, email="c@example.com")
    pid = _add_product(client, stock_quantity=10)
    client.post("/api/cart/items", json={"product_id": pid, "quantity": 1}, headers=auth_header(cust))
    order = client.post("/api/orders", json={"delivery_method": "eco", "delivery_distance": 10},
                        headers=auth_header(cust)).json()
    resp = client.patch(f"/api/admin/orders/{order['id']}", json={"status": "Shipped"},
                        headers=auth_header(token))
    assert resp.status_code == 200 and resp.json()["status"] == "Shipped"


def test_admin_invalid_order_status_rejected(client):
    token = _make_admin(client)
    cust = register(client, email="c2@example.com")
    pid = _add_product(client, stock_quantity=10)
    client.post("/api/cart/items", json={"product_id": pid, "quantity": 1}, headers=auth_header(cust))
    order = client.post("/api/orders", json={"delivery_method": "eco", "delivery_distance": 10},
                        headers=auth_header(cust)).json()
    resp = client.patch(f"/api/admin/orders/{order['id']}", json={"status": "Teleported"},
                        headers=auth_header(token))
    assert resp.status_code == 400
