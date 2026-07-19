"""Provider selection for metadata generation."""

import os

from app.core.config import get_config_value
from app.services.ai.gemini_provider import GeminiMetadataProvider
from app.services.ai.metadata_provider import MetadataProvider
from app.services.ai.mock_provider import MockMetadataProvider
from app.services.ai.openrouter_provider import OpenRouterMetadataProvider


def get_metadata_provider(name: str | None = None) -> MetadataProvider:
    """Return the configured production provider.

    The default provider is determined by the ``METADATA_PROVIDER`` env var
    (``"gemini"``, ``"openrouter"``, or ``"mock"``) and falls back to
    ``"gemini"`` when the variable is unset.
    """
    provider_name = (name or os.getenv("METADATA_PROVIDER", "gemini")).strip().lower()
    if provider_name == "gemini":
        return GeminiMetadataProvider()
    if provider_name == "mock":
        return MockMetadataProvider()
    if provider_name == "openrouter":
        return OpenRouterMetadataProvider()
    raise ValueError(f"Unknown metadata provider: '{provider_name}'")


def metadata_provider_name() -> str:
    """Human-readable active metadata provider name."""
    default = os.getenv("METADATA_PROVIDER", "gemini").strip().lower()
    names = {"gemini": "Gemini", "mock": "Mock", "openrouter": "OpenRouter"}
    return names.get(default, default.capitalize())


def metadata_generation_configured() -> bool:
    """Whether production AI metadata generation has the required API key."""
    provider = os.getenv("METADATA_PROVIDER", "gemini").strip().lower()
    if provider == "openrouter":
        return bool(get_config_value("OPENROUTER_API_KEY"))
    if provider == "mock":
        return True
    return bool(get_config_value("GEMINI_API_KEY"))
