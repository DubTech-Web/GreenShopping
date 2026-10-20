"""Sustainability tests (Spec §9 → Sustainability: carbon calculation, delivery comparison).

Covers the deterministic services directly (fast, no HTTP) and the customer-facing estimate
endpoint (single call returns all options + green recommendation).
"""
from app.database import get_db
from app.models import Product
from app.services import carbon
from app.services.delivery import (
    DELIVERY_OPTIONS,
    delivery_carbon,
    estimate_route_distance_km,
    get_option,
    recommend_greenest,
)
from tests.conftest import auth_header, register


# ---- Service-level: carbon math (Spec §12) ----
def test_product_carbon_sums_factor_times_quantity():
    assert carbon.product_carbon([(2.5, 2), (0.6, 1)]) == 5.6


def test_delivery_carbon_formula():
    eco = get_option("eco")
    # distance * weight * factor = 100 * 1 * 0.004
    assert delivery_carbon(100, 1.0, eco) == 0.4


def test_route_distance_uses_abujas_location_and_road_allowance():
    assert estimate_route_distance_km(9.05785, 7.49508) == 0
    lagos_route = estimate_route_distance_km(6.5244, 3.3792)
    assert 500 < lagos_route < 700


def test_order_total_is_products_plus_delivery():
    est = carbon.estimate_order_carbon(
        product_items=[(2.5, 1), (0.6, 1)],
        weight_items=[(0.5, 1), (0.35, 1)],
        distance_km=100,
        option=get_option("standard"),
    )
    assert est["product_carbon"] == 3.1
    assert est["total_carbon"] == round(est["product_carbon"] + est["delivery_carbon"], 3)
    assert est["unit"] == "kg CO2e" and est["is_estimate"] is True


# ---- Service-level: green delivery comparison (Spec §11) ----
def test_greenest_is_eco_not_cheapest_only():
    # Eco has the lowest emission factor, so it must be recommended.
    assert recommend_greenest(100, 1.0) == "eco"


def test_express_has_highest_emissions():
    est = {opt.key: delivery_carbon(100, 1.0, opt) for opt in DELIVERY_OPTIONS}
    assert est["express"] == max(est.values())
    assert est["eco"] == min(est.values())


# ---- Endpoint-level: single-call estimate powers checkout (Spec §17) ----
def _add_product(client, carbon_factor=2.0, weight=0.5, stock=10):
    db = next(client.app.dependency_overrides[get_db]())
    p = Product(name="Widget", description="d", category="A", price=10.0,
                stock_quantity=stock, weight=weight, eco_score=60, carbon_factor=carbon_factor)
    db.add(p)
    db.commit()
    return p.id


def test_estimate_returns_all_options_and_recommendation(client):
    token = register(client)
    pid = _add_product(client, carbon_factor=2.0, weight=0.5)
    client.post("/api/cart/items", json={"product_id": pid, "quantity": 2},
                headers=auth_header(token))

    resp = client.post("/api/carbon/estimate", json={"delivery_distance": 100},
                       headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["product_carbon"] == 4.0  # 2.0 * 2
    assert len(body["options"]) == 3
    assert body["recommended"] == "eco"  # lowest total carbon
    assert "kg CO2e" in body["reason"] or body["unit"] == "kg CO2e"
    # total = product + that option's delivery
    eco = next(o for o in body["options"] if o["key"] == "eco")
    assert eco["total_carbon"] == round(body["product_carbon"] + eco["delivery_carbon"], 3)


def test_estimate_uses_customer_coordinates_for_route_distance(client):
    token = register(client)
    pid = _add_product(client, carbon_factor=2.0, weight=0.5)
    client.post("/api/cart/items", json={"product_id": pid, "quantity": 2},
                headers=auth_header(token))

    resp = client.post(
        "/api/carbon/estimate",
        json={"latitude": 6.5244, "longitude": 3.3792},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["delivery_distance"] == estimate_route_distance_km(6.5244, 3.3792)
    eco = next(o for o in body["options"] if o["key"] == "eco")
    assert eco["delivery_carbon"] == delivery_carbon(
        body["delivery_distance"], body["package_weight"], get_option("eco")
    )


def test_estimate_empty_cart_rejected(client):
    token = register(client)
    resp = client.post("/api/carbon/estimate", json={"delivery_distance": 100},
                       headers=auth_header(token))
    assert resp.status_code == 400
