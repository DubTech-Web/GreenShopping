"""Authentication endpoints (Spec §6, R1; Phase-2 §1–§6).

Real email-based verification via Resend. The flow:

    register -> account created *unverified* + 6-digit code emailed
    verify-email (email, code) -> account verified + JWT issued
    login (email, password) -> JWT, but only for verified accounts
    resend-code / forgot-password / reset-password -> code-driven, throttled

Design decision (Spec §3 "if appropriate"): verified users log in directly with
email+password rather than receiving a one-time code on every login. Registration already
proves control of the address; a per-login code would add email traffic and requests for no
security gain here — the greener, appropriate choice for this demo. Unverified accounts cannot
obtain a token, satisfying "no protected access before verification" (Spec §1).

Logout is client-side token discard — the stateless JWT means there is no server session to
destroy (matrix Note A), so no endpoint is needed.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_customer
from ..models import Cart, Customer
from ..schemas import (
    CustomerResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ProfileUpdate,
    RegisterRequest,
    ResendCodeRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from ..services import email as email_service
from ..services.security import create_access_token, hash_password, verify_password

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])

# Generic acknowledgement reused so responses don't reveal whether an email exists (Spec §6).
_GENERIC_SENT = "If that account exists and is eligible, a code has been sent."


def _dev_code(code: str) -> str | None:
    """Surface the code to the client ONLY in non-production with Resend disabled (Spec §5).

    In production Resend is enabled and APP_ENV=production, so this always returns None and the
    code travels solely by email.
    """
    return code if (not settings.is_production and not settings.resend_enabled) else None


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> MessageResponse:
    existing = db.scalar(select(Customer).where(Customer.email == payload.email))
    if existing is not None:
        if existing.is_verified:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
        # Unverified re-registration: refresh credentials and re-send a code (no duplicate row).
        existing.name = payload.name
        existing.password_hash = hash_password(payload.password)
        customer = existing
    else:
        customer = Customer(
            name=payload.name,
            email=payload.email,
            password_hash=hash_password(payload.password),
            is_verified=False,
        )
        db.add(customer)
        db.flush()  # assigns customer.id
        db.add(Cart(customer_id=customer.id))  # one cart per customer, created up front

    code = email_service.issue_code(db, customer.id, email_service.EMAIL_VERIFY)
    db.commit()
    email_service.send_code_email(customer.email, code, email_service.EMAIL_VERIFY)
    return MessageResponse(message="Verification code sent to your email.", dev_code=_dev_code(code))


@router.post("/verify-email", response_model=TokenResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> TokenResponse:
    customer = db.scalar(select(Customer).where(Customer.email == payload.email))
    if customer is None or not email_service.verify_code(
        db, customer.id, email_service.EMAIL_VERIFY, payload.code
    ):
        db.commit()  # persist any attempt-counter increment
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    customer.is_verified = True
    db.commit()
    token = create_access_token(customer_id=customer.id, is_admin=customer.is_admin)
    return TokenResponse(access_token=token)


@router.post("/resend-code", response_model=MessageResponse)
def resend_code(payload: ResendCodeRequest, db: Session = Depends(get_db)) -> MessageResponse:
    customer = db.scalar(select(Customer).where(Customer.email == payload.email))
    # Silent no-op for missing/verified accounts — same response either way (no enumeration).
    if customer is None or customer.is_verified:
        return MessageResponse(message=_GENERIC_SENT)

    cooldown = email_service.cooldown_remaining(db, customer.id, email_service.EMAIL_VERIFY)
    if cooldown > 0:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {cooldown}s before requesting another code",
        )

    code = email_service.issue_code(db, customer.id, email_service.EMAIL_VERIFY)
    db.commit()
    email_service.send_code_email(customer.email, code, email_service.EMAIL_VERIFY)
    return MessageResponse(
        message="A new code has been sent.",
        dev_code=_dev_code(code),
        cooldown_seconds=settings.verification_resend_cooldown_seconds,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    customer = db.scalar(select(Customer).where(Customer.email == payload.email))
    if customer is None or not verify_password(payload.password, customer.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not customer.is_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Email not verified")
    token = create_access_token(customer_id=customer.id, is_admin=customer.is_admin)
    return TokenResponse(access_token=token)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    customer = db.scalar(select(Customer).where(Customer.email == payload.email))
    # Always return the same acknowledgement so an attacker can't enumerate accounts (Spec §6).
    if customer is None:
        return MessageResponse(message=_GENERIC_SENT)
    if email_service.cooldown_remaining(db, customer.id, email_service.PASSWORD_RESET) > 0:
        return MessageResponse(message=_GENERIC_SENT)  # silently throttle, don't reveal timing

    code = email_service.issue_code(db, customer.id, email_service.PASSWORD_RESET)
    db.commit()
    email_service.send_code_email(customer.email, code, email_service.PASSWORD_RESET)
    return MessageResponse(message=_GENERIC_SENT, dev_code=_dev_code(code))


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    customer = db.scalar(select(Customer).where(Customer.email == payload.email))
    if customer is None or not email_service.verify_code(
        db, customer.id, email_service.PASSWORD_RESET, payload.code
    ):
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    customer.password_hash = hash_password(payload.new_password)
    customer.is_verified = True  # completing a reset also proves control of the address
    db.commit()
    return MessageResponse(message="Password updated. You can now log in.")


@router.get("/me", response_model=CustomerResponse)
def me(customer: Customer = Depends(get_current_customer)) -> Customer:
    return customer


@router.patch("/me", response_model=CustomerResponse)
def update_me(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
) -> Customer:
    customer.name = payload.name
    db.commit()
    db.refresh(customer)
    return customer
