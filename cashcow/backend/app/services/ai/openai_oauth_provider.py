"""OpenAI OAuth Metadata Provider adapter."""

from app.llm.factory import get_llm_provider
from app.services.ai.metadata_provider import GeminiInvalidJSONError, MetadataGenerationContext, MetadataProvider
from app.prompts.metadata import SYSTEM_PROMPT


class OpenAIOAuthMetadataProvider(MetadataProvider):
    """Adapter bridging MetadataProvider interface with app.llm layer."""

    name = "openai-oauth"
    model = "gpt-5.6-sol"

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.llm = get_llm_provider("openai-oauth")
        if model:
            self.model = model

    def generate(self, context: MetadataGenerationContext) -> dict[str, object]:
        system_prompt = context.system_prompt or SYSTEM_PROMPT
        response = self.llm.generate(prompt=context.final_prompt, system_prompt=system_prompt)
        content = response.content

        from app.services.metadata import parse_json_response
        try:
            return parse_json_response(content)
        except Exception as exc:
            raise GeminiInvalidJSONError(f"Failed to parse JSON from OpenAI OAuth response: {exc}") from exc
