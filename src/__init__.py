"""YouTube CashCow - Automated Video Processing Platform Foundation.

Phase 1 initialization package. Exports app constants, configurations,
validators, and logging subsystems.
"""

from src.config import Settings, load_config
from src.constants import APP_NAME, VERSION
from src.exceptions import (
    CashCowError,
    ConfigurationError,
    DependencyError,
    FolderError,
    ValidationError,
    DownloadError,
    InvalidUrlError,
)
from src.logger import get_logger, init_logger
from src.validator import validate_full_system

__all__ = [
    "APP_NAME",
    "VERSION",
    "Settings",
    "load_config",
    "CashCowError",
    "ConfigurationError",
    "DependencyError",
    "FolderError",
    "ValidationError",
    "DownloadError",
    "InvalidUrlError",
    "get_logger",
    "init_logger",
    "validate_full_system",
]
