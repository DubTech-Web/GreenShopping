"""Reusable FastAPI auth dependencies (Spec §6, §25).

`get_current_customer` protects customer features; `require_admin` gates the admin API.
Both derive identity from the stateless JWT — no session lookup, no extra query beyond
loading the authenticated user once.
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Customer
from .services.security import decode_access_token

_bearer = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)


def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Customer:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        customer_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise invalid

    customer = db.get(Customer, customer_id)  # primary-key fetch, single query
    if customer is None:
        raise invalid
    return customer


def require_admin(customer: Customer = Depends(get_current_customer)) -> Customer:
    if not customer.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return customer


def get_optional_customer(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
    db: Session = Depends(get_db),
) -> Customer | None:
    """Identify the customer if a valid token is present; return None otherwise.

    Lets endpoints (e.g. product detail) personalize when logged in without forcing auth,
    so the same single request serves both anonymous and signed-in visitors (Spec §17).
    """
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        return db.get(Customer, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
