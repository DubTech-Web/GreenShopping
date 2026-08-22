"""Authentication endpoints (Spec §6, R1).

Register, login, and 'me' (protected). Logout is client-side token discard — the stateless
JWT means there is no server session to destroy (matrix Note A), so no endpoint is needed.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_customer
from ..models import Cart, Customer
from ..schemas import (
    CustomerResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from ..services.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    exists = db.scalar(select(Customer.id).where(Customer.email == payload.email))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    customer = Customer(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(customer)
    db.flush()  # assigns customer.id without a second round trip
    db.add(Cart(customer_id=customer.id))  # one cart per customer, created up front
    db.commit()

    token = create_access_token(customer_id=customer.id, is_admin=customer.is_admin)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    customer = db.scalar(select(Customer).where(Customer.email == payload.email))
    # Verify even when the user is missing? No — but return an identical error either way.
    if customer is None or not verify_password(payload.password, customer.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    token = create_access_token(customer_id=customer.id, is_admin=customer.is_admin)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=CustomerResponse)
def me(customer: Customer = Depends(get_current_customer)) -> Customer:
    return customer
