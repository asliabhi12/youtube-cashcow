"""Provider selection for metadata generation."""

from app.core.config import get_config_value
from app.services.ai.gemini_provider import GeminiMetadataProvider
from app.services.ai.metadata_provider import MetadataProvider
from app.services.ai.mock_provider import MockMetadataProvider


def get_metadata_provider(name: str | None = None) -> MetadataProvider:
    """Return the configured production provider."""
    provider_name = (name or "gemini").strip().lower()
    if provider_name == "gemini":
        return GeminiMetadataProvider()
    if provider_name == "mock":
        return MockMetadataProvider()
    raise ValueError(f"Unknown metadata provider: '{provider_name}'")


def metadata_provider_name() -> str:
    """Human-readable active metadata provider name."""
    return "Gemini"


def metadata_generation_configured() -> bool:
    """Whether production AI metadata generation has the required API key."""
    return bool(get_config_value("GEMINI_API_KEY"))
