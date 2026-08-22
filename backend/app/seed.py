"""Seed a small, realistic dataset (Spec §23).

Deliberately small (~24 products, a few customers, a few orders) to keep processing light.
Sufficient to demonstrate recommendations, inventory, reports, carbon, and green delivery.

Run:  python -m app.seed          (idempotent: recreates a fresh database)
"""
from __future__ import annotations

from .database import Base, SessionLocal, engine
from .models import (
    Cart,
    Customer,
    Order,
    OrderItem,
    Product,
    RecommendationInteraction,
)
from .services import carbon
from .services.delivery import get_option
from .services.security import hash_password

# (name, category, price, stock, weight_kg, eco_score, carbon_factor, is_eco, low_stock)
# Categories intentionally contain eco/standard pairs so eco-alternatives exist (Spec §10B).
PRODUCTS: list[tuple] = [
    # Drinkware — standard vs. eco pairs
    ("Standard Plastic Water Bottle", "Drinkware", 4.99, 40, 0.10, 25, 2.5, False, 8),
    ("Reusable Stainless Steel Bottle", "Drinkware", 18.99, 30, 0.35, 90, 0.6, True, 5),
    ("Bamboo Travel Mug", "Drinkware", 15.50, 25, 0.30, 85, 0.7, True, 5),
    ("Disposable Cup Pack (50)", "Drinkware", 6.49, 60, 0.50, 20, 3.0, False, 10),
    # Bags
    ("Single-Use Plastic Bags (100)", "Bags", 3.99, 50, 0.40, 15, 2.8, False, 10),
    ("Organic Cotton Tote Bag", "Bags", 12.99, 35, 0.25, 88, 0.5, True, 5),
    ("Jute Shopping Bag", "Bags", 9.99, 28, 0.30, 82, 0.6, True, 5),
    # Kitchen
    ("Plastic Food Wrap", "Kitchen", 3.49, 45, 0.20, 18, 2.2, False, 8),
    ("Beeswax Food Wraps (3)", "Kitchen", 14.99, 22, 0.15, 86, 0.4, True, 5),
    ("Bamboo Cutlery Set", "Kitchen", 11.99, 30, 0.20, 84, 0.5, True, 5),
    ("Compostable Bin Liners (30)", "Kitchen", 7.99, 40, 0.35, 80, 0.9, True, 8),
    # Personal care
    ("Plastic Toothbrush (4pk)", "Personal Care", 4.29, 50, 0.10, 22, 1.8, False, 10),
    ("Bamboo Toothbrush (4pk)", "Personal Care", 8.99, 38, 0.08, 87, 0.4, True, 6),
    ("Solid Shampoo Bar", "Personal Care", 9.49, 33, 0.12, 89, 0.3, True, 6),
    ("Natural Loofah Sponge", "Personal Care", 5.99, 27, 0.05, 83, 0.2, True, 5),
    # Home
    ("Incandescent Bulb (4pk)", "Home", 6.99, 40, 0.30, 30, 2.0, False, 8),
    ("LED Light Bulb (4pk)", "Home", 13.99, 45, 0.25, 78, 0.8, True, 8),
    ("Recycled Paper Towels (6)", "Home", 8.49, 36, 0.90, 72, 1.1, True, 8),
    ("Soy Wax Candle", "Home", 16.99, 3, 0.40, 81, 0.7, True, 4),  # seeded low-stock (demo §13)
    # Stationery
    ("Plastic Ballpoint Pens (20)", "Stationery", 5.49, 55, 0.25, 24, 1.5, False, 10),
    ("Recycled Notebook", "Stationery", 7.49, 42, 0.30, 79, 0.6, True, 8),
    ("Refillable Fountain Pen", "Stationery", 19.99, 2, 0.10, 76, 0.5, True, 4),  # low-stock (demo §13)
    # Electronics accessories
    ("Standard Phone Case", "Electronics", 9.99, 30, 0.05, 35, 1.6, False, 6),
    ("Biodegradable Phone Case", "Electronics", 17.99, 24, 0.05, 85, 0.4, True, 5),
]

CUSTOMERS: list[tuple] = [
    ("Admin User", "admin@example.com", "adminpass123", True),
    ("Ada Green", "ada@example.com", "password123", False),
    ("Ben Rivers", "ben@example.com", "password123", False),
    ("Chidi Okafor", "chidi@example.com", "password123", False),
]

# (customer_email, [(product_name, qty), ...], delivery_key, distance_km)
ORDERS: list[tuple] = [
    ("ada@example.com", [("Reusable Stainless Steel Bottle", 1), ("Bamboo Toothbrush (4pk)", 2)], "eco", 40),
    ("ada@example.com", [("Organic Cotton Tote Bag", 1), ("Solid Shampoo Bar", 1)], "standard", 120),
    ("ben@example.com", [("LED Light Bulb (4pk)", 2), ("Recycled Notebook", 3)], "express", 300),
    ("ben@example.com", [("Beeswax Food Wraps (3)", 2)], "eco", 25),
    ("chidi@example.com", [("Standard Plastic Water Bottle", 4), ("Disposable Cup Pack (50)", 1)], "standard", 90),
    ("chidi@example.com", [("Biodegradable Phone Case", 1), ("Bamboo Cutlery Set", 2)], "eco", 60),
]


def seed() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        products = {
            row[0]: Product(
                name=row[0], description=f"{row[0]} — category {row[1]}.", category=row[1],
                price=row[2], stock_quantity=row[3], weight=row[4], eco_score=row[5],
                carbon_factor=row[6], is_eco_friendly=row[7], low_stock_threshold=row[8],
            )
            for row in PRODUCTS
        }
        db.add_all(products.values())

        customers = {
            email: Customer(name=name, email=email, password_hash=hash_password(pw), is_admin=is_admin)
            for name, email, pw, is_admin in CUSTOMERS
        }
        db.add_all(customers.values())
        db.flush()

        for cust in customers.values():
            db.add(Cart(customer_id=cust.id))

        for email, lines, delivery_key, distance in ORDERS:
            option = get_option(delivery_key)
            cust = customers[email]
            line_products = [(products[name], qty) for name, qty in lines]

            estimate = carbon.estimate_order_carbon(
                product_items=[(p.carbon_factor, qty) for p, qty in line_products],
                weight_items=[(p.weight, qty) for p, qty in line_products],
                distance_km=distance, option=option,
            )
            total = round(sum(float(p.price) * qty for p, qty in line_products), 2)

            order = Order(
                customer_id=cust.id, total_amount=total, delivery_method=delivery_key,
                delivery_distance=distance, carbon_impact=estimate["total_carbon"],
                delivery_carbon=estimate["delivery_carbon"], status="Delivered",
            )
            db.add(order)
            db.flush()
            for product, qty in line_products:
                db.add(OrderItem(order_id=order.id, product_id=product.id, quantity=qty, unit_price=product.price))
                product.stock_quantity -= qty
                db.add(RecommendationInteraction(customer_id=cust.id, product_id=product.id, interaction_type="purchase"))

        db.commit()

    print(f"Seeded {len(PRODUCTS)} products, {len(CUSTOMERS)} customers, {len(ORDERS)} orders.")
    print("Admin login: admin@example.com / adminpass123")


if __name__ == "__main__":
    seed()
