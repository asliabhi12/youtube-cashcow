"""Custom exception hierarchy for the YouTube CashCow application.

Provides specific, typed errors to assist in debugging and robust error handling.
"""


class CashCowError(Exception):
    """Base exception for all YouTube CashCow errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(CashCowError):
    """Raised when application configuration loading or validation fails."""


class ValidationError(CashCowError):
    """Raised when general system validation (e.g., Python version) fails."""


class FolderError(CashCowError):
    """Raised when there are issues creating, checking, or writing to required directories."""


class DependencyError(CashCowError):
    """Raised when required package dependencies are missing."""


class DownloadError(CashCowError):
    """Raised when a media download operation fails."""


class InvalidUrlError(CashCowError):
    """Raised when a URL is malformed or not supported by the system."""

