"""Email verification codes + delivery (Spec Phase-2 §1, §2, §5, §6).

Security properties (Spec §2):
- Codes are generated with the ``secrets`` CSPRNG, 6 digits.
- Only a SHA-256 hash is stored — never the plaintext code.
- Codes expire and are single-use (consumed on success).
- A per-purpose attempt cap and a resend cooldown throttle brute force / abuse.

Delivery (``send_email``): the configured primary provider (Brevo in production, SMTP locally),
then the other provider as a fallback. When neither is configured
(local dev / tests) nothing is emailed; instead the caller may surface a ``dev_code`` in the
response, but ONLY in non-production with no email provider (see routers/auth). Delivery never
raises to the caller and codes are never logged in production (Spec §2, §6).
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Order, VerificationCode

logger = logging.getLogger("greenshopping.email")

_BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
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
    settings = get_settings()
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
    settings = get_settings()
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
    settings = get_settings()
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


def _format_money(amount: float) -> str:
    return f"₦{amount:,.2f}"


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send an HTML email via the preferred provider and then its configured fallback.

    Returns True if sent successfully, False otherwise (never raises exceptions to caller):
    a transient mail outage must never 500 a registration or reveal which addresses exist.
    """
    settings = get_settings()
    providers = (
        ("brevo", "smtp")
        if settings.preferred_email_provider == "brevo"
        else ("smtp", "brevo")
    )
    for provider in providers:
        if provider == "brevo" and settings.brevo_enabled:
            try:
                with httpx.Client(timeout=_TIMEOUT) as http:
                    resp = http.post(
                        _BREVO_ENDPOINT,
                        headers={
                            "accept": "application/json",
                            "api-key": settings.brevo_api_key,
                            "content-type": "application/json",
                        },
                        json={
                            "sender": {
                                "name": settings.brevo_from_name,
                                "email": settings.brevo_from_email,
                            },
                            "to": [{"email": to_email}],
                            "subject": subject,
                            "htmlContent": html_content,
                        },
                    )
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                logger.warning("Brevo connection failed (%s); trying fallback", type(exc).__name__)
                continue
            except httpx.HTTPError as exc:
                # A timeout or transport error after sending may mean Brevo accepted the message.
                logger.warning(
                    "Brevo request outcome is uncertain (%s); skipping fallback",
                    type(exc).__name__,
                )
                break

            if resp.is_success:
                logger.info("Email sent via Brevo")
                return True
            if resp.status_code >= 500 or resp.status_code == 408:
                logger.warning(
                    "Brevo returned HTTP %s; delivery may be uncertain, skipping fallback",
                    resp.status_code,
                )
                break
            logger.warning("Brevo rejected the request with HTTP %s; trying fallback", resp.status_code)
        elif provider == "smtp" and settings.smtp_enabled:
            submission_started = False
            try:
                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = settings.smtp_from_email or f"GreenShopping <{settings.smtp_user}>"
                msg["To"] = to_email
                msg.set_content("Please view this email in an HTML-compatible email client.")
                msg.add_alternative(html_content, subtype="html")

                if settings.smtp_use_ssl or settings.smtp_port == 465:
                    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                        server.login(settings.smtp_user, settings.smtp_password)
                        server.send_message(msg)
                else:
                    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                        if settings.smtp_use_tls:
                            server.starttls()
                        server.login(settings.smtp_user, settings.smtp_password)
                        submission_started = True
                        server.send_message(msg)
                logger.info("Email sent via SMTP")
                return True
            except (smtplib.SMTPException, OSError) as exc:
                logger.warning("SMTP delivery failed (%s)", type(exc).__name__)
                if submission_started:
                    break

    return False


def send_code_email(to_email: str, code: str, purpose: str) -> bool:
    """Email the code via the configured provider and return whether delivery succeeded."""
    settings = get_settings()

    ttl = settings.verification_code_ttl_minutes
    action = "verify your email" if purpose == EMAIL_VERIFY else "reset your password"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>{_SUBJECTS.get(purpose, 'GreenShopping Code')}</title></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background-color:#f4f6f0;margin:0;padding:24px;color:#1c2b16;">
      <div style="max-width:540px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e1e7d5;box-shadow:0 2px 8px rgba(0,0,0,0.04);">
        <div style="background:#284320;color:#ffffff;padding:24px;text-align:center;">
          <h1 style="margin:0;font-size:22px;font-weight:700;letter-spacing:-0.02em;">🌿 GreenShopping</h1>
        </div>
        <div style="padding:32px 24px;">
          <h2 style="margin-top:0;font-size:18px;color:#1c2b16;">Your Verification Code</h2>
          <p style="color:#4a5b44;font-size:15px;line-height:1.5;">Use the 6-digit code below to {action}:</p>
          <div style="background:#edf3e5;border:1.5px dashed #7ea367;border-radius:8px;padding:16px;text-align:center;margin:24px 0;">
            <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#284320;font-family:monospace;">{code}</span>
          </div>
          <p style="color:#6b7c65;font-size:13px;line-height:1.4;">
            This code expires in <strong>{ttl} minutes</strong>. If you did not request this, please safely ignore this email.
          </p>
        </div>
        <div style="background:#f9faf6;padding:16px;text-align:center;font-size:12px;color:#8a9984;border-top:1px solid #edf0e7;">
          GreenShopping · AI-Powered Sustainable E-Commerce
        </div>
      </div>
    </body>
    </html>
    """
    return send_email(to_email, _SUBJECTS.get(purpose, "Your GreenShopping code"), html)


def send_order_confirmation_email(order: Order, customer_email: str) -> None:
    """Send an itemized order confirmation email with sustainable receipt details."""
    subject = f"Order #{order.id} Confirmed - GreenShopping Receipt 🌿"

    items_rows = ""
    for item in order.items:
        line_total = float(item.unit_price) * item.quantity
        items_rows += f"""
        <tr style="border-bottom:1px solid #edf0e7;">
          <td style="padding:10px 8px;font-size:14px;color:#1c2b16;">{item.product.name}</td>
          <td style="padding:10px 8px;font-size:14px;color:#4a5b44;text-align:center;">{item.quantity}</td>
          <td style="padding:10px 8px;font-size:14px;color:#4a5b44;text-align:right;">{_format_money(float(item.unit_price))}</td>
          <td style="padding:10px 8px;font-size:14px;color:#1c2b16;font-weight:600;text-align:right;">{_format_money(line_total)}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>{subject}</title></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background-color:#f4f6f0;margin:0;padding:24px;color:#1c2b16;">
      <div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e1e7d5;box-shadow:0 2px 10px rgba(0,0,0,0.05);">
        <div style="background:#284320;color:#ffffff;padding:24px 28px;text-align:center;">
          <h1 style="margin:0;font-size:22px;font-weight:700;">🌿 GreenShopping</h1>
          <p style="margin:6px 0 0;font-size:14px;color:#d7e6ae;">Thank you for shopping sustainably!</p>
        </div>
        <div style="padding:28px 24px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;border-bottom:2px solid #edf0e7;padding-bottom:16px;">
            <div>
              <h2 style="margin:0;font-size:18px;color:#1c2b16;">Order #{order.id}</h2>
              <span style="display:inline-block;margin-top:4px;padding:3px 10px;background:#edf3e5;color:#284320;border-radius:999px;font-size:12px;font-weight:700;">Status: Paid</span>
            </div>
            <div style="text-align:right;color:#6b7c65;font-size:13px;">
              Date: {order.created_at.strftime('%b %d, %Y')}
            </div>
          </div>

          <h3 style="font-size:15px;color:#1c2b16;margin:16px 0 8px;">Purchased Items</h3>
          <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
            <thead>
              <tr style="background:#f7f9f3;border-bottom:1.5px solid #e1e7d5;font-size:12px;text-transform:uppercase;color:#6b7c65;">
                <th style="padding:8px;text-align:left;">Item</th>
                <th style="padding:8px;text-align:center;">Qty</th>
                <th style="padding:8px;text-align:right;">Price</th>
                <th style="padding:8px;text-align:right;">Total</th>
              </tr>
            </thead>
            <tbody>
              {items_rows}
            </tbody>
          </table>

          <div style="background:#f7f9f3;border-radius:8px;padding:16px;margin:20px 0;border:1px solid #e5ecd9;">
            <div style="display:flex;justify-content:space-between;padding:4px 0;font-size:14px;">
              <span style="color:#4a5b44;">Delivery Method:</span>
              <strong style="text-transform:capitalize;color:#1c2b16;">{order.delivery_method} ({order.delivery_distance} km)</strong>
            </div>
            <div style="display:flex;justify-content:space-between;padding:4px 0;font-size:14px;">
              <span style="color:#4a5b44;">Estimated Carbon Impact:</span>
              <strong style="color:#3e6b2e;">{order.carbon_impact:.2f} kg CO₂e</strong>
            </div>
            <div style="display:flex;justify-content:space-between;padding:8px 0 0;margin-top:6px;border-top:1.5px solid #e1e7d5;font-size:16px;">
              <span style="font-weight:700;color:#1c2b16;">Total Amount Paid:</span>
              <strong style="font-size:18px;color:#1c2b16;">{_format_money(float(order.total_amount))}</strong>
            </div>
          </div>

          <p style="color:#6b7c65;font-size:13px;line-height:1.4;margin-top:20px;">
            Your order is being processed for dispatch. You can track your order status anytime on your GreenShopping dashboard.
          </p>
        </div>
        <div style="background:#f9faf6;padding:16px;text-align:center;font-size:12px;color:#8a9984;border-top:1px solid #edf0e7;">
          GreenShopping · Delivering thoughtful choices with a lighter footprint 🌱
        </div>
      </div>
    </body>
    </html>
    """
    send_email(customer_email, subject, html)
