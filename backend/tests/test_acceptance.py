"""End-to-end acceptance test — the full workflow from Spec §32.

Exercises the entire customer + admin journey against the real app, asserting every step the
final acceptance test names. One test, one story.
"""
from app.database import get_db
from app.models import Customer
from app.services.security import hash_password
from tests.conftest import auth_header


def _make_admin(client):
    db = next(client.app.dependency_overrides[get_db]())
    db.add(Customer(name="Admin", email="admin@example.com",
                    password_hash=hash_password("adminpass123"), is_admin=True))
    db.commit()
    return client.post("/api/auth/login",
                       json={"email": "admin@example.com", "password": "adminpass123"}
                       ).json()["access_token"]


def _seed_catalog(client):
    """A standard product and its greener same-category alternative."""
    admin = _make_admin(client)
    std = client.post("/api/admin/products", headers=auth_header(admin), json={
        "name": "Standard Water Bottle", "category": "Drinkware", "price": 5.0,
        "stock_quantity": 10, "weight": 0.1, "eco_score": 25, "carbon_factor": 2.5,
        "is_eco_friendly": False,
    }).json()
    client.post("/api/admin/products", headers=auth_header(admin), json={
        "name": "Reusable Steel Bottle", "category": "Drinkware", "price": 18.0,
        "stock_quantity": 10, "weight": 0.35, "eco_score": 90, "carbon_factor": 0.6,
        "is_eco_friendly": True,
    })
    return admin, std["id"]


def test_full_acceptance_workflow(client):
    admin, std_id = _seed_catalog(client)

    # 1. Customer registers.
    token = client.post("/api/auth/register", json={
        "name": "Journey User", "email": "journey@example.com", "password": "password123",
    }).json()["access_token"]
    hdr = auth_header(token)

    # 2. Customer logs in (implicit — token issued). 3. Browses products.
    catalog = client.get("/api/products").json()
    assert catalog["meta"]["total"] >= 2

    # 4. Views a product → 5. system provides recommendations → 6. sees eco-friendly alternative.
    detail = client.get(f"/api/products/{std_id}", headers=hdr).json()
    assert detail["recommendations"], "expected similar-product recommendations"
    assert detail["eco_alternative"] is not None
    assert detail["eco_alternative"]["eco_score"] > detail["eco_score"]

    # 7. Adds product to cart.
    cart = client.post("/api/cart/items", json={"product_id": std_id, "quantity": 2}, headers=hdr).json()
    assert cart["item_count"] == 2

    # 8. Checks out → 9. system calculates carbon impact → 10. delivery options shown +
    # 11. greener delivery recommended.
    estimate = client.post("/api/carbon/estimate", json={"delivery_distance": 100}, headers=hdr).json()
    assert estimate["product_carbon"] > 0
    assert len(estimate["options"]) == 3
    assert estimate["recommended"] == "eco"  # greener, not cheapest-only

    # 12. Places order.
    order = client.post("/api/orders", json={"delivery_method": "eco", "delivery_distance": 100},
                        headers=hdr).json()
    assert order["carbon_impact"] > 0
    assert order["total_amount"] == 10.0  # 2 x 5.0

    # 13. Inventory decreases (10 - 2 = 8). 14. Order recorded.
    assert client.get(f"/api/products/{std_id}").json()["stock_quantity"] == 8
    assert len(client.get("/api/orders", headers=hdr).json()) == 1

    # 15. Admin sees the order.
    admin_orders = client.get("/api/admin/orders", headers=auth_header(admin)).json()["items"]
    assert any(o["id"] == order["id"] for o in admin_orders)

    # 16. Admin sees inventory update.
    admin_products = client.get("/api/admin/products", headers=auth_header(admin)).json()["items"]
    assert next(p for p in admin_products if p["id"] == std_id)["stock_quantity"] == 8

    # 17. Admin sees sales report. 18. Admin sees sustainability report.
    sales = client.get("/api/reports/sales", headers=auth_header(admin)).json()
    assert sales["total_sales"] == 10.0
    sust = client.get("/api/reports/sustainability", headers=auth_header(admin)).json()
    assert sust["eco_delivery_percentage"] == 100.0  # the one order used eco delivery
    assert sust["total_estimated_co2"] > 0
