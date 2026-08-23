"""Paystack payment integration (Spec Phase-2 §9–§12).

The backend is authoritative about money. Two rules that this module enforces:

1. The charged amount is ALWAYS ``settings.payment_amount_kobo`` (₦100). It is never derived
   from the cart total and never read from the frontend (Spec §10, §12, §32).
2. An order is only ever marked Paid after a *server-side* verification call to Paystack
   confirms the transaction succeeded for that exact amount (Spec §11).

When ``PAYSTACK_SECRET_KEY`` is unset (local dev / tests) the module runs in **simulation
mode**: it issues a clearly-marked ``gs_sim_`` reference and verification succeeds locally, so
the whole checkout flow is exercisable offline. Simulated references are only ever accepted
while Paystack is disabled — once a real key is present, every reference is verified against
the live API, so a simulated reference cannot bypass a real charge.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass

import httpx

from ..config import get_settings

settings = get_settings()

_PAYSTACK_BASE = "https://api.paystack.co"
_TIMEOUT = httpx.Timeout(15.0)
_SIM_PREFIX = "gs_sim_"


@dataclass(frozen=True)
class PaymentInit:
    reference: str
    amount_kobo: int
    public_key: str
    email: str
    simulated: bool
    authorization_url: str | None = None
    access_code: str | None = None


def _new_reference(simulated: bool) -> str:
    return (_SIM_PREFIX if simulated else "gs_") + secrets.token_hex(12)


def initialize(*, email: str, order_id: int) -> PaymentInit:
    """Start a transaction for the fixed demo amount and return what the frontend needs.

    In simulation mode this makes no network call. In live mode it initializes the transaction
    with our own reference so verification later is deterministic.
    """
    amount = settings.payment_amount_kobo

    if not settings.paystack_enabled:
        return PaymentInit(
            reference=_new_reference(simulated=True),
            amount_kobo=amount,
            public_key=settings.paystack_public_key,
            email=email,
            simulated=True,
        )

    reference = _new_reference(simulated=False)
    callback_url = f"{settings.frontend_url.rstrip('/')}/orders/{order_id}" if settings.frontend_url else None
    payload: dict[str, object] = {"email": email, "amount": amount, "reference": reference}
    if callback_url:
        payload["callback_url"] = callback_url

    with httpx.Client(timeout=_TIMEOUT) as http:
        resp = http.post(
            f"{_PAYSTACK_BASE}/transaction/initialize",
            headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
            json=payload,
        )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    return PaymentInit(
        reference=reference,
        amount_kobo=amount,
        public_key=settings.paystack_public_key,
        email=email,
        simulated=False,
        authorization_url=data.get("authorization_url"),
        access_code=data.get("access_code"),
    )


def verify(reference: str) -> bool:
    """Return True only if the transaction genuinely succeeded for the fixed amount.

    Simulated references are accepted only while Paystack is disabled. Any network/API failure
    is treated as *not verified* (fail closed) so an order is never wrongly marked Paid.
    """
    if not settings.paystack_enabled:
        return reference.startswith(_SIM_PREFIX)

    # Live mode: a simulated reference must never pass.
    if reference.startswith(_SIM_PREFIX):
        return False

    try:
        with httpx.Client(timeout=_TIMEOUT) as http:
            resp = http.get(
                f"{_PAYSTACK_BASE}/transaction/verify/{reference}",
                headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
            )
        resp.raise_for_status()
        data = resp.json().get("data", {})
    except (httpx.HTTPError, ValueError):
        return False

    # Authoritative amount check: reject if Paystack reports a different amount than we set.
    return data.get("status") == "success" and int(data.get("amount", 0)) == settings.payment_amount_kobo
