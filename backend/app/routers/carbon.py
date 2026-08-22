"""Carbon footprint preview endpoint (Spec §12, §11, §17).

ONE call powers the entire checkout impact panel: given the authenticated cart and a
distance, it returns the product carbon plus every delivery option's carbon and the combined
total, along with the recommended greener option (lowest total carbon — not cheapest). The
frontend switches delivery methods client-side with no further requests (Spec §17, §21).

All figures are ESTIMATES in kg CO2e (Spec §12).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_customer
from ..models import Customer
from ..schemas import DeliveryOptionEstimate, EstimateRequest, EstimateResponse
from ..services import carbon
from ..services.cart_query import load_cart_items
from ..services.delivery import DELIVERY_OPTIONS, delivery_carbon

router = APIRouter(prefix="/api/carbon", tags=["carbon"])


@router.post("/estimate", response_model=EstimateResponse)
def estimate(
    payload: EstimateRequest,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
) -> EstimateResponse:
    items = load_cart_items(db, customer.id)
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    product_carbon = carbon.product_carbon(
        [(i.product.carbon_factor, i.quantity) for i in items]
    )
    weight = carbon.total_package_weight([(i.product.weight, i.quantity) for i in items])

    options = [
        DeliveryOptionEstimate(
            key=opt.key,
            label=opt.label,
            speed=opt.speed,
            cost=opt.cost,
            emission_factor=opt.emission_factor,
            delivery_carbon=(dc := delivery_carbon(payload.delivery_distance, weight, opt)),
            total_carbon=round(product_carbon + dc, 3),
        )
        for opt in DELIVERY_OPTIONS
    ]

    greenest = min(options, key=lambda o: o.total_carbon)
    dirtiest = max(options, key=lambda o: o.total_carbon)
    saved = round(dirtiest.total_carbon - greenest.total_carbon, 3)
    reason = (
        f"{greenest.label} has the lowest estimated total impact "
        f"({greenest.total_carbon} kg CO2e) — about {saved} kg CO2e less than {dirtiest.label}."
    )

    return EstimateResponse(
        product_carbon=product_carbon,
        package_weight=weight,
        options=options,
        recommended=greenest.key,
        reason=reason,
    )
