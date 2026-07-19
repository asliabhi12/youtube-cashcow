"""Gemini-backed YouTube metadata provider."""

from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.config import DEFAULT_GEMINI_MODEL, get_config_value
from app.services.ai.metadata_provider import (
    MetadataGenerationContext,
    MetadataProvider,
    MetadataProviderError,
)

logger = logging.getLogger(__name__)

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_SECONDS = 30


class GeminiMetadataProvider(MetadataProvider):
    """Generate YouTube metadata through Google Gemini."""

    name = "gemini"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or get_config_value("GEMINI_API_KEY")
        self.model = model or get_config_value("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL

    def generate(self, context: MetadataGenerationContext) -> dict[str, object]:
        if not self._api_key:
            raise MetadataProviderError("GEMINI_API_KEY is not configured")

        request = Request(
            _generate_content_url(self.model),
            data=json.dumps(_build_payload(context)).encode("utf-8"),
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = _read_error_body(exc)
            raise MetadataProviderError(
                f"Gemini API error {exc.code}: {detail or exc.reason}"
            ) from exc
        except (TimeoutError, URLError) as exc:
            raise MetadataProviderError(f"Gemini API request failed: {exc}") from exc

        logger.info("Complete Gemini HTTP response body: %s", response_body)
        content = _extract_message_content(response_body)
        return _parse_metadata_json(content)


def _generate_content_url(model: str) -> str:
    model_name = model if model.startswith("models/") else f"models/{model}"
    return f"{GEMINI_API_BASE_URL}/{quote(model_name, safe='/')}:generateContent"


def _build_payload(context: MetadataGenerationContext) -> dict[str, object]:
    return {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": _build_prompt(context)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1200,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["title", "description", "tags"],
            },
        },
    }


def _build_prompt(context: MetadataGenerationContext) -> str:
    return "\n\n".join(
        [
            context.final_prompt,
            "Return ONLY valid JSON in this exact format:",
            '{\n  "title": "...",\n  "description": "...",\n  "tags": ["...", "...", "..."]\n}',
            "No markdown. No code fences. No explanations.",
        ]
    )


def _extract_message_content(response_body: str) -> str:
    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError as exc:
        logger.warning("Gemini response body is not valid JSON: %s", exc)
        raise MetadataProviderError("Gemini API returned a malformed response") from exc

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        logger.warning("Gemini response has no candidates array or the array is empty")
        raise MetadataProviderError("Gemini API returned no candidates")

    first_candidate = candidates[0]
    if not isinstance(first_candidate, dict):
        logger.warning("Gemini first candidate is not an object: %r", first_candidate)
        raise MetadataProviderError("Gemini API returned a malformed candidate")

    content_payload = first_candidate.get("content")
    if not isinstance(content_payload, dict):
        logger.warning("Gemini first candidate has no content object: %r", first_candidate)
        raise MetadataProviderError("Gemini API returned no content")

    parts = content_payload.get("parts")
    if not isinstance(parts, list) or not parts:
        logger.warning("Gemini content has no parts array or the array is empty: %r", content_payload)
        raise MetadataProviderError("Gemini API returned no content parts")

    text_parts: list[str] = []
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            logger.warning("Gemini part %s is not an object: %r", index, part)
            continue
        text = part.get("text")
        if isinstance(text, str):
            text_parts.append(text)
        else:
            logger.warning("Gemini part %s has no text field: %r", index, part)

    content = "".join(text_parts)
    if not content.strip():
        logger.warning("Gemini response did not contain any non-empty text parts")
        raise MetadataProviderError("Gemini API returned an empty response")
    logger.info(
        "Raw extracted Gemini text:\n----- BEGIN GEMINI TEXT -----\n%s\n----- END GEMINI TEXT -----",
        content,
    )
    return content.strip()


def _parse_metadata_json(content: str) -> dict[str, object]:
    content = _strip_markdown_code_fence(content)
    logger.info("Text passed to json.loads:\n----- BEGIN GEMINI TEXT -----\n%s\n----- END GEMINI TEXT -----", content)
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise MetadataProviderError("Gemini API returned invalid JSON metadata") from exc
    if not isinstance(payload, dict):
        raise MetadataProviderError("Gemini API returned metadata that is not an object")
    return payload


def _strip_markdown_code_fence(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if not lines:
        return stripped
    opening = lines[0].strip().lower()
    if opening not in {"```", "```json"}:
        return stripped
    if len(lines) > 1 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return "\n".join(lines[1:]).strip()


def _read_error_body(exc: HTTPError) -> str:
    try:
        return exc.read().decode("utf-8").strip()
    except Exception:  # noqa: BLE001 - best-effort diagnostic only
        return ""
