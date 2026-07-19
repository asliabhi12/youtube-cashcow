"""Deterministic local provider used until a hosted AI provider is configured."""

from typing import Any

from app.models.metadata import TITLE_MAX_LENGTH
from app.services.ai.metadata_provider import MetadataGenerationContext, MetadataProvider


class MockMetadataProvider(MetadataProvider):
    name = "mock"
    model = "mock-v1"

    def generate(self, context: MetadataGenerationContext) -> dict[str, Any]:
        """Create useful, deterministic defaults from the assembled AI input."""
        seed = context.title_seed or context.original_title or context.output_filename or "this video"
        title = f"{seed.strip()} | Polished YouTube Title"[:TITLE_MAX_LENGTH]
        description_parts = [
            f"A polished YouTube description based on: {seed.strip()}",
            context.creative_profile_prompt,
        ]
        if context.video_duration is not None:
            description_parts.append(f"Duration: {context.video_duration:g} seconds.")
        if context.detected_language:
            description_parts.append(f"Language: {context.detected_language}.")
        tags = ["youtube", "video", *context.keywords, *context.topics]
        return {
            "title": title,
            "description": "\n\n".join(description_parts),
            "tags": tags[:20],
        }
