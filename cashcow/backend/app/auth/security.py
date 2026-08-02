"""Security utilities for CashCow authentication.

Provides password verification via Argon2, session token generation via HMAC-SHA256,
and IP-based login rate limiting.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.auth.config import (
    MAX_LOGIN_ATTEMPTS,
    RATE_LIMIT_WINDOW_SECONDS,
    SESSION_DURATION_REMEMBER,
    SESSION_DURATION_STANDARD,
    get_admin_password,
    get_admin_username,
    get_secret_key,
)

logger = logging.getLogger(__name__)

_ph = PasswordHasher()

# Rate limiting in-memory store: IP -> list of attempt timestamps
_failed_attempts: dict[str, list[float]] = {}


def verify_password(plain_password: str) -> bool:
    """Verify a plain password against the current configured admin password using Argon2."""
    configured_password = get_admin_password()
    try:
        current_hash = _ph.hash(configured_password)
        _ph.verify(current_hash, plain_password)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False
    except Exception as err:
        logger.error("Password verification error: %s", err)
        return hmac.compare_digest(plain_password, configured_password)


def is_rate_limited(ip_address: str) -> bool:
    """Check if an IP address has exceeded failed login attempt threshold."""
    now = time.time()
    attempts = _failed_attempts.get(ip_address, [])
    # Filter attempts within rate limit window
    recent = [t for t in attempts if now - t < RATE_LIMIT_WINDOW_SECONDS]
    _failed_attempts[ip_address] = recent
    return len(recent) >= MAX_LOGIN_ATTEMPTS


def record_failed_attempt(ip_address: str) -> None:
    """Record a failed login attempt for an IP address."""
    now = time.time()
    attempts = _failed_attempts.get(ip_address, [])
    attempts.append(now)
    _failed_attempts[ip_address] = attempts


def clear_failed_attempts(ip_address: str) -> None:
    """Clear failed attempts for an IP address on successful login."""
    _failed_attempts.pop(ip_address, None)


def create_session_token(username: str, remember_me: bool) -> tuple[str, int]:
    """Create a signed session token. Returns (token, expires_at_timestamp)."""
    duration = SESSION_DURATION_REMEMBER if remember_me else SESSION_DURATION_STANDARD
    now = int(time.time())
    expires_at = now + duration

    payload = {
        "sub": username,
        "iat": now,
        "exp": expires_at,
        "remember": remember_me,
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")

    secret = get_secret_key()
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    token = f"{payload_b64}.{signature}"
    return token, expires_at


def verify_session_token(token: str) -> Optional[dict[str, Any]]:
    """Verify session token HMAC signature and expiration."""
    if not token or "." not in token:
        return None

    try:
        payload_b64, signature = token.split(".", 1)
        secret = get_secret_key()
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Re-pad base64 string
        padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Check expiration
        now = int(time.time())
        if payload.get("exp", 0) <= now:
            return None

        # Check sub matches current configured admin username
        admin_user = get_admin_username()
        if payload.get("sub") != admin_user:
            return None

        return payload
    except Exception as err:
        logger.warning("Token verification failed: %s", err)
        return None
