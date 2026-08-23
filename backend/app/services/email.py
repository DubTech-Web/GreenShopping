"""Email verification codes + Resend delivery (Spec Phase-2 §1, §2, §5, §6).

Security properties (Spec §2):
- Codes are generated with the ``secrets`` CSPRNG, 6 digits.
- Only a SHA-256 hash is stored — never the plaintext code.
- Codes expire and are single-use (consumed on success).
- A per-purpose attempt cap and a resend cooldown throttle brute force / abuse.

Delivery: when ``RESEND_API_KEY`` is set, the code is emailed via Resend's REST API (no SDK
dependency — one ``httpx`` POST). When it is unset (local dev / tests) nothing is emailed;
instead the caller may surface a ``dev_code`` in the response, but ONLY in non-production with
Resend disabled (see routers/auth). Codes are never logged in production (Spec §2).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import VerificationCode

settings = get_settings()

_RESEND_ENDPOINT = "https://api.resend.com/emails"
_TIMEOUT = httpx.Timeout(15.0)

EMAIL_VERIFY = "email_verify"
PASSWORD_RESET = "password_reset"

_SUBJECTS = {
    EMAIL_VERIFY: "Your GreenShopping verification code",
    PASSWORD_RESET: "Your GreenShopping password reset code",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _as_aware(dt: datetime) -> datetime:
    """SQLite may return naive datetimes; treat stored timestamps as UTC for comparison."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def cooldown_remaining(db: Session, customer_id: int, purpose: str) -> int:
    """Seconds left before another code may be requested (0 if allowed now) — Spec §2."""
    latest = db.scalar(
        select(VerificationCode)
        .where(VerificationCode.customer_id == customer_id, VerificationCode.purpose == purpose)
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    if latest is None:
        return 0
    elapsed = (_utcnow() - _as_aware(latest.created_at)).total_seconds()
    remaining = settings.verification_resend_cooldown_seconds - int(elapsed)
    return max(remaining, 0)


def issue_code(db: Session, customer_id: int, purpose: str) -> str:
    """Create and persist a fresh code, invalidating any prior unconsumed code for the purpose.

    Returns the plaintext code so the caller can email it (or surface it in dev). Does NOT
    commit — the caller owns the transaction.
    """
    # Invalidate older outstanding codes so only the newest is ever valid (single active code).
    for old in db.scalars(
        select(VerificationCode).where(
            VerificationCode.customer_id == customer_id,
            VerificationCode.purpose == purpose,
            VerificationCode.consumed_at.is_(None),
        )
    ):
        old.consumed_at = _utcnow()

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        VerificationCode(
            customer_id=customer_id,
            purpose=purpose,
            code_hash=_hash_code(code),
            expires_at=_utcnow() + timedelta(minutes=settings.verification_code_ttl_minutes),
        )
    )
    return code


def verify_code(db: Session, customer_id: int, purpose: str, code: str) -> bool:
    """Check a submitted code: single-use, unexpired, attempt-capped (Spec §2).

    Consumes the code on success. On failure, increments the attempt counter and consumes the
    code once the cap is hit (forcing the user to request a new one). Does NOT commit.
    """
    record = db.scalar(
        select(VerificationCode)
        .where(
            VerificationCode.customer_id == customer_id,
            VerificationCode.purpose == purpose,
            VerificationCode.consumed_at.is_(None),
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    if record is None:
        return False
    if _as_aware(record.expires_at) < _utcnow():
        return False
    if record.attempts >= settings.verification_max_attempts:
        record.consumed_at = _utcnow()
        return False

    if not secrets.compare_digest(record.code_hash, _hash_code(code)):
        record.attempts += 1
        if record.attempts >= settings.verification_max_attempts:
            record.consumed_at = _utcnow()  # lock out after too many tries
        return False

    record.consumed_at = _utcnow()  # single-use
    return True


def send_code_email(to_email: str, code: str, purpose: str) -> None:
    """Email the code via Resend. No-op when Resend is not configured (dev/test).

    Failures are swallowed (logged, not raised) so a transient email outage cannot 500 a
    registration and cannot be used to probe which emails exist (Spec §6 enumeration note).
    """
    if not settings.resend_enabled:
        return

    ttl = settings.verification_code_ttl_minutes
    action = "verify your email" if purpose == EMAIL_VERIFY else "reset your password"
    html = (
        f"<div style='font-family:system-ui,sans-serif;font-size:16px;color:#1c2b16'>"
        f"<p>Use this code to {action}:</p>"
        f"<p style='font-size:28px;font-weight:700;letter-spacing:4px'>{code}</p>"
        f"<p>It expires in {ttl} minutes. If you didn't request this, you can ignore this email.</p>"
        f"</div>"
    )
    try:
        with httpx.Client(timeout=_TIMEOUT) as http:
            http.post(
                _RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.resend_from_email,
                    "to": [to_email],
                    "subject": _SUBJECTS[purpose],
                    "html": html,
                },
            ).raise_for_status()
    except httpx.HTTPError:
        # Deliberately silent: never reveal delivery success/failure to the caller.
        pass
