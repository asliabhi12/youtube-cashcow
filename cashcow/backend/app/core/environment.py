"""Environment enum and detection for CashCow."""

from enum import Enum
import os


class Environment(str, Enum):
    DEVELOPMENT = "dev"
    TESTING = "test"
    PRODUCTION = "prod"


def get_current_environment() -> Environment:
    raw = os.getenv("CASHCOW_ENV", "").strip().lower()
    if raw in {"test", "testing", "pytest"} or "pytest" in os.getenv("PYTEST_CURRENT_TEST", ""):
        return Environment.TESTING
    if raw in {"prod", "production"}:
        return Environment.PRODUCTION
    return Environment.DEVELOPMENT
