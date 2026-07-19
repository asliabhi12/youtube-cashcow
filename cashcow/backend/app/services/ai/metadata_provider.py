"""Abstract interface for AI metadata providers."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field


class MetadataGenerationContext(BaseModel):
    """Complete input a metadata provider receives for one generation."""

    model_config = ConfigDict(extra="forbid")

    system_prompt: str
    creative_profile_prompt: str
    title_seed: str | None = None
    original_title: str | None = None
    video_duration: float | None = None
    transcript: str | None = None
    detected_language: str | None = None
    output_filename: str | None = None
    topics: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    final_prompt: str


class MetadataProviderError(RuntimeError):
    """A metadata provider failed in a recoverable way."""


class MetadataProvider(ABC):
    """Generate metadata without coupling the service to a specific AI SDK."""

    name: str
    model: str

    @abstractmethod
    def generate(self, context: MetadataGenerationContext) -> dict[str, object]:
        """Return structured metadata fields for ``context``."""
