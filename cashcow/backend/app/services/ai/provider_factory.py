"""Provider selection for metadata generation."""

import os

from app.core.config import get_app_config, get_config_value
from app.services.ai.gemini_provider import GeminiMetadataProvider
from app.services.ai.metadata_provider import MetadataProvider
from app.services.ai.mock_provider import MockMetadataProvider
from app.services.ai.openai_oauth_provider import OpenAIOAuthMetadataProvider
from app.services.ai.openrouter_provider import OpenRouterMetadataProvider


def get_metadata_provider(name: str | None = None) -> MetadataProvider:
    """Return the configured production provider.

    The default provider is determined by ``AI_PROVIDER`` or ``METADATA_PROVIDER``
    (``"openai-oauth"``, ``"gemini"``, ``"openrouter"``, or ``"mock"``).
    """
    provider_name = (
        name
        or os.getenv("AI_PROVIDER")
        or os.getenv("METADATA_PROVIDER")
        or get_app_config().ai_provider
    ).strip().lower()

    if provider_name in {"openai-oauth", "openai_oauth", "openai"}:
        return OpenAIOAuthMetadataProvider()
    if provider_name == "gemini":
        return GeminiMetadataProvider()
    if provider_name == "mock":
        return MockMetadataProvider()
    if provider_name == "openrouter":
        return OpenRouterMetadataProvider()
    raise ValueError(f"Unknown metadata provider: '{provider_name}'")


def metadata_provider_name() -> str:
    """Human-readable active metadata provider name."""
    default = (
        os.getenv("AI_PROVIDER")
        or os.getenv("METADATA_PROVIDER")
        or get_app_config().ai_provider
    ).strip().lower()
    names = {
        "openai-oauth": "OpenAI OAuth",
        "openai_oauth": "OpenAI OAuth",
        "gemini": "Gemini",
        "mock": "Mock",
        "openrouter": "OpenRouter",
    }
    return names.get(default, default.capitalize())


def metadata_generation_configured() -> bool:
    """Whether production AI metadata generation is configured."""
    provider = (
        os.getenv("AI_PROVIDER")
        or os.getenv("METADATA_PROVIDER")
        or get_app_config().ai_provider
    ).strip().lower()
    if provider in {"openai-oauth", "openai_oauth", "openai"}:
        return True
    if provider == "openrouter":
        return bool(get_config_value("OPENROUTER_API_KEY"))
    if provider == "mock":
        return True
    return bool(get_config_value("GEMINI_API_KEY"))
