"""Green delivery options and emissions (Spec §11, R6/G1).

Delivery options are static configuration — three fixed methods whose characteristics never
change at runtime — so they are not a database table (matrix Note B; Spec §5). Emissions are
a deterministic calculation, never an AI/network call (Spec §19).

Emission factors are illustrative academic estimates (kg CO2e per kg-km), documented in
docs/green-software.md. They are chosen so a ~100 km, ~1 kg parcel lands near the spec's
0.70 kg CO2e example for Standard delivery.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryOption:
    key: str
    label: str
    speed: str
    cost: float  # currency units
    emission_factor: float  # kg CO2e per (kg * km)


# Ordered cheapest-emissions first is NOT assumed anywhere; the recommender computes it.
DELIVERY_OPTIONS: tuple[DeliveryOption, ...] = (
    DeliveryOption("eco", "Eco Delivery", "5–7 days", 2.99, 0.004),
    DeliveryOption("standard", "Standard Delivery", "3–4 days", 4.99, 0.007),
    DeliveryOption("express", "Express Delivery", "1 day", 12.99, 0.015),
)

_OPTIONS_BY_KEY = {opt.key: opt for opt in DELIVERY_OPTIONS}


def get_option(key: str) -> DeliveryOption | None:
    return _OPTIONS_BY_KEY.get(key)


def delivery_carbon(distance_km: float, package_weight_kg: float, option: DeliveryOption) -> float:
    """delivery_carbon = distance x weight x emission_factor (Spec §11)."""
    return round(distance_km * package_weight_kg * option.emission_factor, 3)


def recommend_greenest(distance_km: float, package_weight_kg: float) -> str:
    """Return the option key with the lowest estimated carbon — NOT simply the cheapest (§11)."""
    return min(
        DELIVERY_OPTIONS,
        key=lambda opt: delivery_carbon(distance_km, package_weight_kg, opt),
    ).key


def options_with_estimates(distance_km: float, package_weight_kg: float) -> dict:
    """All options with per-option carbon estimate, plus the greener recommendation + reason."""
    options = [
        {
            "key": opt.key,
            "label": opt.label,
            "speed": opt.speed,
            "cost": opt.cost,
            "emission_factor": opt.emission_factor,
            "carbon_estimate": delivery_carbon(distance_km, package_weight_kg, opt),
        }
        for opt in DELIVERY_OPTIONS
    ]
    recommended = recommend_greenest(distance_km, package_weight_kg)
    greenest = min(options, key=lambda o: o["carbon_estimate"])
    dirtiest = max(options, key=lambda o: o["carbon_estimate"])
    saved = round(dirtiest["carbon_estimate"] - greenest["carbon_estimate"], 3)
    reason = (
        f"Lowest estimated carbon impact ({greenest['carbon_estimate']} kg CO2e), "
        f"about {saved} kg CO2e less than {dirtiest['label']}."
    )
    return {"options": options, "recommended": recommended, "reason": reason}
