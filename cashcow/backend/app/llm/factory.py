"""Factory for LLM providers."""

from app.core.config import get_config_value
from app.llm.base import LLMProvider
from app.llm.openai_oauth import OpenAIOAuthProvider


def get_llm_provider(provider_type: str | None = None) -> LLMProvider:
    """Return configured LLM provider instance.

    Reads provider configuration from:
    - AI_PROVIDER / LLM_PROVIDER (default: "openai-oauth")
    - AI_BASE_URL / OPENAI_OAUTH_BASE_URL (default: "http://127.0.0.1:10531/v1")
    - AI_MODEL / GPT_MODEL (default: "gpt-5.6-sol")
    """
    provider = (
        provider_type
        or get_config_value("AI_PROVIDER")
        or get_config_value("LLM_PROVIDER")
        or "openai-oauth"
    ).strip().lower()

    base_url = (
        get_config_value("AI_BASE_URL")
        or get_config_value("OPENAI_OAUTH_BASE_URL")
        or "http://127.0.0.1:10531/v1"
    )

    model = (
        get_config_value("AI_MODEL")
        or get_config_value("GPT_MODEL")
        or "gpt-5.6-sol"
    )

    if provider in {"openai-oauth", "openai_oauth", "openai"}:
        return OpenAIOAuthProvider(base_url=base_url, model=model)

    raise ValueError(f"Unsupported AI_PROVIDER: '{provider}'")
