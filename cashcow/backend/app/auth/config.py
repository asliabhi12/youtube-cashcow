"""Authentication configuration settings for CashCow."""

import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

from app.core.config import get_config_value, _dotenv_paths

# Load environment variables from .env files
for path in _dotenv_paths():
    if path.exists():
        load_dotenv(path)


def get_admin_username() -> str:
    """Dynamically get configured admin username from env or .env file."""
    return (
        get_config_value("CASHCOW_ADMIN_USER")
        or get_config_value("ADMIN_USERNAME")
        or "admin"
    )


def get_admin_password() -> str:
    """Dynamically get configured admin password from env or .env file."""
    return (
        get_config_value("CASHCOW_ADMIN_PASSWORD")
        or get_config_value("ADMIN_PASSWORD")
        or "admin"
    )


def get_secret_key() -> str:
    """Dynamically get configured secret key from env or .env file."""
    return (
        get_config_value("CASHCOW_SECRET_KEY")
        or get_config_value("SECRET_KEY")
        or "default_cashcow_secret_key_change_me_in_prod"
    )


# Session Durations (seconds)
SESSION_DURATION_STANDARD: int = 24 * 3600        # 24 Hours (86,400s)
SESSION_DURATION_REMEMBER: int = 30 * 24 * 3600    # 30 Days (2,592,000s)

# Rate Limiting: Max 5 failed login attempts per 60 seconds per IP
MAX_LOGIN_ATTEMPTS: int = 5
RATE_LIMIT_WINDOW_SECONDS: int = 60

COOKIE_NAME: str = "cashcow_session"
