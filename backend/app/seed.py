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

# (name, category, price_naira, stock, weight_kg, eco_score, carbon_factor, is_eco, low_stock)
# Prices are realistic Nigerian Naira values (Spec Phase-2 §31). Categories intentionally
# contain eco/standard pairs so eco-alternatives exist (Spec §10B).
PRODUCTS: list[tuple] = [
    # Drinkware — standard vs. eco pairs
    ("Standard Plastic Water Bottle", "Drinkware", 5000, 40, 0.10, 25, 2.5, False, 8),
    ("Reusable Stainless Steel Bottle", "Drinkware", 18500, 30, 0.35, 90, 0.6, True, 5),
    ("Bamboo Travel Mug", "Drinkware", 15500, 25, 0.30, 85, 0.7, True, 5),
    ("Disposable Cup Pack (50)", "Drinkware", 6500, 60, 0.50, 20, 3.0, False, 10),
    # Bags
    ("Single-Use Plastic Bags (100)", "Bags", 4000, 50, 0.40, 15, 2.8, False, 10),
    ("Organic Cotton Tote Bag", "Bags", 13000, 35, 0.25, 88, 0.5, True, 5),
    ("Jute Shopping Bag", "Bags", 10000, 28, 0.30, 82, 0.6, True, 5),
    # Kitchen
    ("Plastic Food Wrap", "Kitchen", 3500, 45, 0.20, 18, 2.2, False, 8),
    ("Beeswax Food Wraps (3)", "Kitchen", 15000, 22, 0.15, 86, 0.4, True, 5),
    ("Bamboo Cutlery Set", "Kitchen", 12000, 30, 0.20, 84, 0.5, True, 5),
    ("Compostable Bin Liners (30)", "Kitchen", 8000, 40, 0.35, 80, 0.9, True, 8),
    # Personal care
    ("Plastic Toothbrush (4pk)", "Personal Care", 4300, 50, 0.10, 22, 1.8, False, 10),
    ("Bamboo Toothbrush (4pk)", "Personal Care", 9000, 38, 0.08, 87, 0.4, True, 6),
    ("Solid Shampoo Bar", "Personal Care", 9500, 33, 0.12, 89, 0.3, True, 6),
    ("Natural Loofah Sponge", "Personal Care", 6000, 27, 0.05, 83, 0.2, True, 5),
    # Home
    ("Incandescent Bulb (4pk)", "Home", 7000, 40, 0.30, 30, 2.0, False, 8),
    ("LED Light Bulb (4pk)", "Home", 14000, 45, 0.25, 78, 0.8, True, 8),
    ("Recycled Paper Towels (6)", "Home", 8500, 36, 0.90, 72, 1.1, True, 8),
    ("Soy Wax Candle", "Home", 17000, 3, 0.40, 81, 0.7, True, 4),  # seeded low-stock (demo §13)
    # Stationery
    ("Plastic Ballpoint Pens (20)", "Stationery", 5500, 55, 0.25, 24, 1.5, False, 10),
    ("Recycled Notebook", "Stationery", 7500, 42, 0.30, 79, 0.6, True, 8),
    ("Refillable Fountain Pen", "Stationery", 20000, 2, 0.10, 76, 0.5, True, 4),  # low-stock (demo §13)
    # Electronics accessories
    ("Standard Phone Case", "Electronics", 10000, 30, 0.05, 35, 1.6, False, 6),
    ("Biodegradable Phone Case", "Electronics", 18000, 24, 0.05, 85, 0.4, True, 5),
]

IMAGE_URLS = {
    "Standard Plastic Water Bottle": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=640&q=75",
    "Reusable Stainless Steel Bottle": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=640&q=75",
    "Bamboo Travel Mug": "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?auto=format&fit=crop&w=640&q=75",
    "Disposable Cup Pack (50)": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?auto=format&fit=crop&w=640&q=75",
    "Single-Use Plastic Bags (100)": "https://images.unsplash.com/photo-1610824352934-c10d87b700cc?auto=format&fit=crop&w=640&q=75",
    "Organic Cotton Tote Bag": "https://images.unsplash.com/photo-1597484662317-9bd7bffa8e84?auto=format&fit=crop&w=640&q=75",
    "Jute Shopping Bag": "https://images.unsplash.com/photo-1597484662317-9bd7bffa8e84?auto=format&fit=crop&w=640&q=75",
    "Plastic Food Wrap": "https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=640&q=75",
    "Beeswax Food Wraps (3)": "https://images.unsplash.com/photo-1600185365926-3a2ce3cdb9eb?auto=format&fit=crop&w=640&q=75",
    "Bamboo Cutlery Set": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=640&q=75",
    "Compostable Bin Liners (30)": "https://images.unsplash.com/photo-1583947215259-38e31be8751f?auto=format&fit=crop&w=640&q=75",
    "Plastic Toothbrush (4pk)": "https://images.unsplash.com/photo-1609840114035-3c981b782dfe?auto=format&fit=crop&w=640&q=75",
    "Bamboo Toothbrush (4pk)": "https://images.unsplash.com/photo-1609840114035-3c981b782dfe?auto=format&fit=crop&w=640&q=75",
    "Solid Shampoo Bar": "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?auto=format&fit=crop&w=640&q=75",
    "Natural Loofah Sponge": "https://images.unsplash.com/photo-1583947215259-38e31be8751f?auto=format&fit=crop&w=640&q=75",
    "Incandescent Bulb (4pk)": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=640&q=75",
    "LED Light Bulb (4pk)": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=640&q=75",
    "Recycled Paper Towels (6)": "https://images.unsplash.com/photo-1583947215259-38e31be8751f?auto=format&fit=crop&w=640&q=75",
    "Soy Wax Candle": "https://images.unsplash.com/photo-1603006905003-be475563bc59?auto=format&fit=crop&w=640&q=75",
    "Plastic Ballpoint Pens (20)": "https://images.unsplash.com/photo-1455390582262-044cdaad277a?auto=format&fit=crop&w=640&q=75",
    "Recycled Notebook": "https://images.unsplash.com/photo-1455390582262-044cdaad277a?auto=format&fit=crop&w=640&q=75",
    "Refillable Fountain Pen": "https://images.unsplash.com/photo-1455390582262-044cdaad277a?auto=format&fit=crop&w=640&q=75",
    "Standard Phone Case": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=640&q=75",
    "Biodegradable Phone Case": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=640&q=75",
}

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
                name=row[0], image_url=IMAGE_URLS[row[0]], description=f"{row[0]} — category {row[1]}.", category=row[1],
                price=row[2], stock_quantity=row[3], weight=row[4], eco_score=row[5],
                carbon_factor=row[6], is_eco_friendly=row[7], low_stock_threshold=row[8],
            )
            for row in PRODUCTS
        }
        db.add_all(products.values())

        customers = {
            email: Customer(
                name=name, email=email, password_hash=hash_password(pw),
                is_admin=is_admin, is_verified=True,  # seeded accounts are pre-verified for the demo
            )
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
                stock_deducted=True,  # delivered orders have committed their inventory (§13)
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
