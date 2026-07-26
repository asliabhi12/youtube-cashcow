"""Abstract base provider interface for LLM operations."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class LLMResponse(BaseModel):
    """Structured response from LLM provider including text content and execution statistics."""

    model_config = ConfigDict(extra="ignore")

    content: str
    model: str | None = None
    duration_seconds: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate response from the provider with exponential backoff and timeout."""
        pass
