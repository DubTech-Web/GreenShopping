"""Security: password hashing and JWT (Spec §6, §25).

Password hashing uses the standard library's PBKDF2-HMAC-SHA256 — secure, and it adds no
dependency or native build (greener than bcrypt/passlib; matrix Note in architecture §6).
Tokens are stateless JWTs (HS256) so no server-side session store is needed (Spec §29).
"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from ..config import get_settings

_PBKDF2_ROUNDS = 200_000  # OWASP-aligned work factor for PBKDF2-HMAC-SHA256
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Return 'pbkdf2_sha256$rounds$salt_hex$hash_hex' (self-describing, verifiable later)."""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification against a stored hash. Returns False on any format error."""
    try:
        algorithm, rounds_s, salt_hex, hash_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        expected = bytes.fromhex(hash_hex)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds_s)
        )
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest, expected)


def create_access_token(*, customer_id: int, is_admin: bool) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(customer_id), "is_admin": is_admin, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode/verify a token. Raises jwt.PyJWTError on invalid/expired tokens."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
