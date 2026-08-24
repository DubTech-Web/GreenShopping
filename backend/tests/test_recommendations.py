"""Recommendation engine tests (Spec §9 → AI: recommendations, eco alternatives)."""
from app.database import get_db
from app.models import Product
from app.services import recommender
from tests.conftest import auth_header, register


def _p(**kw) -> Product:
    base = dict(name="X", description="d", category="Drinkware", price=10.0,
                stock_quantity=10, weight=0.5, eco_score=50, carbon_factor=1.0,
                is_eco_friendly=False)
    base.update(kw)
    p = Product(**base)
    return p


# ---- Service-level (pure algorithm) ----
def test_similar_prefers_same_category():
    seed = _p(name="Standard Bottle", category="Drinkware", eco_score=30, carbon_factor=2.5)
    seed.id = 1
    same = _p(name="Steel Bottle", category="Drinkware", eco_score=90, carbon_factor=0.6)
    same.id = 2
    other = _p(name="Notebook", category="Stationery", eco_score=80, carbon_factor=0.6)
    other.id = 3
    ranked = recommender.recommend_similar(seed, [same, other], limit=2)
    assert ranked[0].product.id == 2  # same category ranks first
    assert ranked[0].reason  # explanation present


def test_eco_alternative_is_strictly_greener():
    seed = _p(name="Standard Bottle", eco_score=30, carbon_factor=2.5)
    seed.id = 1
    greener = _p(name="Steel Bottle", eco_score=90, carbon_factor=0.6)
    greener.id = 2
    worse = _p(name="Cheap Bottle", eco_score=20, carbon_factor=3.0)
    worse.id = 3
    alt = recommender.find_eco_alternative(seed, [greener, worse])
    assert alt is not None and alt.product.id == 2
    assert "eco score" in alt.reason.lower()


def test_no_eco_alternative_when_seed_is_greenest():
    seed = _p(eco_score=95, carbon_factor=0.3)
    seed.id = 1
    other = _p(eco_score=40, carbon_factor=2.0)
    other.id = 2
    assert recommender.find_eco_alternative(seed, [other]) is None


def test_exclude_ids_removes_owned_products():
    seed = _p(name="Bottle A")
    seed.id = 1
    cand = _p(name="Bottle B")
    cand.id = 2
    assert recommender.recommend_similar(seed, [cand], exclude_ids={2}) == []


# ---- Endpoint-level: bundled into product detail (Spec §17) ----
def _seed_pair(client):
    db = next(client.app.dependency_overrides[get_db]())
    standard = Product(name="Standard Plastic Bottle", description="plastic bottle",
                       category="Drinkware", price=5.0, stock_quantity=10, weight=0.1,
                       eco_score=25, carbon_factor=2.5, is_eco_friendly=False)
    steel = Product(name="Reusable Steel Bottle", description="steel bottle",
                    category="Drinkware", price=18.0, stock_quantity=10, weight=0.35,
                    eco_score=90, carbon_factor=0.6, is_eco_friendly=True)
    db.add_all([standard, steel])
    db.commit()
    return standard.id, steel.id


def test_product_detail_bundles_recommendations(client):
    standard_id, steel_id = _seed_pair(client)
    resp = client.get(f"/api/products/{standard_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "recommendations" in body and "eco_alternative" in body
    assert body["eco_alternative"]["id"] == steel_id  # greener same-category item
    assert body["eco_alternative"]["reason"]


def test_customer_specific_excludes_purchased(client):
    """Signed-in customer who bought the steel bottle no longer sees it recommended."""
    standard_id, steel_id = _seed_pair(client)
    token = register(client, email="buyer@example.com")
    # Buy the steel bottle and complete payment so interaction is recorded.
    client.post("/api/cart/items", json={"product_id": steel_id, "quantity": 1},
                headers=auth_header(token))
    ord_resp = client.post("/api/orders", json={"delivery_method": "eco", "delivery_distance": 10},
                           headers=auth_header(token))
    init = client.post("/api/payments/init", json={"order_id": ord_resp.json()["id"]},
                       headers=auth_header(token)).json()
    client.post("/api/payments/verify", json={"reference": init["reference"]},
                headers=auth_header(token))

    body = client.get(f"/api/products/{standard_id}", headers=auth_header(token)).json()
    rec_ids = [r["id"] for r in body["recommendations"]]
    assert steel_id not in rec_ids  # already purchased -> excluded
