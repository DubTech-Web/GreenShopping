"""Reports tests (Spec §9 → Reports: sales calculations, sustainability calculations).

Totals are asserted against a known small fixture so the SQL aggregation is verified end to
end, including the eco-delivery percentage and the reduction-vs-express baseline.
"""
from app.database import get_db
from app.models import Customer, Product
from app.services.security import hash_password
from tests.conftest import auth_header, register


def _admin_token(client):
    db = next(client.app.dependency_overrides[get_db]())
    db.add(Customer(name="Admin", email="admin@example.com",
                    password_hash=hash_password("adminpass123"), is_admin=True, is_verified=True))
    db.commit()
    return client.post("/api/auth/login",
                       json={"email": "admin@example.com", "password": "adminpass123"}
                       ).json()["access_token"]


def _product(client, **kw):
    db = next(client.app.dependency_overrides[get_db]())
    base = dict(name="P", description="d", category="A", price=10.0, stock_quantity=100,
                weight=0.5, eco_score=60, carbon_factor=1.0, is_eco_friendly=False)
    base.update(kw)
    p = Product(**base)
    db.add(p)
    db.commit()
    return p.id


def _order(client, token, pid, qty, method, distance):
    client.post("/api/cart/items", json={"product_id": pid, "quantity": qty},
                headers=auth_header(token))
    ord_resp = client.post("/api/orders", json={"delivery_method": method, "delivery_distance": distance},
                           headers=auth_header(token))
    order_id = ord_resp.json()["id"]
    init = client.post("/api/payments/init", json={"order_id": order_id}, headers=auth_header(token)).json()
    client.post("/api/payments/verify", json={"reference": init["reference"]}, headers=auth_header(token))
    return ord_resp


def _build_fixture(client):
    """2 orders: one eco (eco product), one express (standard product)."""
    admin = _admin_token(client)
    cust = register(client, email="cust@example.com")
    eco_pid = _product(client, name="Eco Item", price=20.0, eco_score=90,
                       carbon_factor=0.5, is_eco_friendly=True)
    std_pid = _product(client, name="Std Item", price=10.0, eco_score=30,
                       carbon_factor=2.0, is_eco_friendly=False)
    _order(client, cust, eco_pid, 2, "eco", 50)       # revenue 40
    _order(client, cust, std_pid, 1, "express", 100)  # revenue 10
    return admin, eco_pid, std_pid


def test_dashboard_metrics(client):
    admin, *_ = _build_fixture(client)
    m = client.get("/api/reports/dashboard", headers=auth_header(admin)).json()
    assert m["total_orders"] == 2
    assert m["total_sales"] == 50.0             # 40 + 10
    assert m["eco_delivery_percentage"] == 50.0  # 1 of 2 orders eco
    assert m["total_estimated_co2"] > 0


def test_sales_report_best_sellers_and_categories(client):
    admin, eco_pid, _ = _build_fixture(client)
    r = client.get("/api/reports/sales", headers=auth_header(admin)).json()
    assert r["total_sales"] == 50.0
    # Eco item sold 2 units -> top seller.
    assert r["best_sellers"][0]["product_id"] == eco_pid
    assert r["best_sellers"][0]["units_sold"] == 2
    assert sum(c["value"] for c in r["sales_by_category"]) == 50.0


def test_sustainability_report(client):
    admin, *_ = _build_fixture(client)
    s = client.get("/api/reports/sustainability", headers=auth_header(admin)).json()
    assert s["eco_delivery_count"] == 1
    assert s["eco_delivery_percentage"] == 50.0
    assert s["eco_products_sold_units"] == 2       # 2 eco units sold
    assert s["average_co2_per_order"] > 0
    # Eco order could have been express -> positive estimated saving.
    assert s["estimated_co2_saved_vs_express"] > 0
    assert s["unit"] == "kg CO2e"


def test_reports_require_admin(client):
    token = register(client, email="notadmin@example.com")
    assert client.get("/api/reports/dashboard", headers=auth_header(token)).status_code == 403
