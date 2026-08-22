"""Carbon footprint estimator (Spec §12, R7/G5).

Transparent, deterministic estimate — never an AI/network call (Spec §19):

    product_carbon = Σ (product.carbon_factor * quantity)
    order_carbon   = product_carbon + delivery_carbon

All values are ESTIMATES in kg CO2e and are labelled as such in the API/UI. The computed
order total is stored on the order for sustainability reporting (Spec §12, §15).
"""
from collections.abc import Iterable

from .delivery import DeliveryOption, delivery_carbon


def product_carbon(items: Iterable[tuple[float, int]]) -> float:
    """items = iterable of (carbon_factor, quantity)."""
    return round(sum(factor * qty for factor, qty in items), 3)


def total_package_weight(items: Iterable[tuple[float, int]]) -> float:
    """items = iterable of (weight_kg, quantity)."""
    return round(sum(weight * qty for weight, qty in items), 3)


def estimate_order_carbon(
    *,
    product_items: list[tuple[float, int]],
    weight_items: list[tuple[float, int]],
    distance_km: float,
    option: DeliveryOption,
) -> dict:
    """Return the itemised estimate: products, delivery, and total (all kg CO2e)."""
    products = product_carbon(product_items)
    weight = total_package_weight(weight_items)
    delivery = delivery_carbon(distance_km, weight, option)
    return {
        "product_carbon": products,
        "delivery_carbon": delivery,
        "total_carbon": round(products + delivery, 3),
        "package_weight": weight,
        "unit": "kg CO2e",
        "is_estimate": True,
    }
