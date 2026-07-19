"""Gemini-backed YouTube metadata provider."""

from __future__ import annotations

import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.config import DEFAULT_GEMINI_MODEL, get_config_value
from app.services.ai.metadata_provider import (
    GeminiAPIError,
    GeminiAuthenticationError,
    GeminiEmptyResponseError,
    GeminiInvalidJSONError,
    GeminiRateLimitError,
    GeminiTimeoutError,
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
        job_id = context.job_id or "unknown"
        start_time = time.monotonic()

        if not self._api_key:
            logger.info("[Job %s] Model name: %s", job_id, self.model)
            logger.info("[Job %s] Final prompt: %s", job_id, context.final_prompt)
            logger.error("[Job %s] Authentication error: GEMINI_API_KEY is not configured", job_id)
            raise GeminiAuthenticationError("GEMINI_API_KEY is not configured")

        prompt = _build_prompt(context)
        payload = _build_payload(context)
        logger.info("[Job %s] Final prompt length: %d characters", job_id, len(context.final_prompt))
        logger.info("[Job %s] Transcript length: %d characters", job_id, len(context.transcript or ""))
        logger.info("[Job %s] Model: %s", job_id, self.model)
        logger.info("[Job %s] Request payload (generation config): %s", job_id, json.dumps(payload.get("generationConfig", {})))

        request = Request(
            _generate_content_url(self.model),
            data=json.dumps(payload).encode("utf-8"),
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
                duration = time.monotonic() - start_time
                logger.info("[Job %s] Response status: 200", job_id)
                logger.info("[Job %s] Request duration: %.2fs", job_id, duration)
                logger.info("[Job %s] Raw response text: %s", job_id, response_body)
        except HTTPError as exc:
            duration = time.monotonic() - start_time
            detail = _read_error_body(exc)
            logger.info("[Job %s] Response status: %s", job_id, exc.code)
            logger.info("[Job %s] Request duration: %.2fs", job_id, duration)
            logger.info("[Job %s] Raw response text: %s", job_id, detail)
            if exc.code in (401, 403):
                logger.error("[Job %s] Authentication failed: Gemini API returned status %s", job_id, exc.code)
                raise GeminiAuthenticationError(
                    f"Authentication failed: Gemini API error {exc.code}: {detail or exc.reason}"
                ) from exc
            elif exc.code == 429:
                logger.error("[Job %s] Rate limited: Gemini API returned status 429", job_id)
                raise GeminiRateLimitError(
                    f"Rate limited: Gemini API error {exc.code}: {detail or exc.reason}"
                ) from exc
            else:
                logger.error("[Job %s] API error: Gemini API returned status %s", job_id, exc.code)
                raise GeminiAPIError(
                    f"API error: Gemini API error {exc.code}: {detail or exc.reason}"
                ) from exc
        except (TimeoutError, URLError) as exc:
            duration = time.monotonic() - start_time
            logger.info("[Job %s] Response status: Connection error/Timeout", job_id)
            logger.info("[Job %s] Request duration: %.2fs", job_id, duration)
            logger.info("[Job %s] Raw response text: None", job_id)
            if isinstance(exc, TimeoutError):
                logger.error("[Job %s] Timeout: Gemini API request timed out after %ds", job_id, REQUEST_TIMEOUT_SECONDS)
                raise GeminiTimeoutError(
                    f"Timeout: Gemini API request timed out after {REQUEST_TIMEOUT_SECONDS}s"
                ) from exc
            logger.error("[Job %s] API error: Gemini API request failed: %s", job_id, exc)
            raise GeminiAPIError(f"API error: Gemini API request failed: {exc}") from exc

        logger.info("[Job %s] Complete Gemini HTTP response body: %s", job_id, response_body)
        content = _extract_message_content(response_body, job_id)
        logger.info("[Job %s] Extracted candidate text: %s", job_id, content)
        parsed_json = _parse_metadata_json(content, job_id)
        logger.info("[Job %s] Parsed JSON: %s", job_id, json.dumps(parsed_json, ensure_ascii=False))
        return parsed_json


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
            "maxOutputTokens": 8192,
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


def _extract_message_content(response_body: str, job_id: str = "unknown") -> str:
    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError as exc:
        logger.warning("[Job %s] Gemini response body is not valid JSON: %s", job_id, exc)
        raise GeminiInvalidJSONError("Invalid JSON: Gemini API returned a malformed response") from exc

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        logger.warning("[Job %s] No candidates returned: Gemini response has no candidates array or the array is empty", job_id)
        raise GeminiEmptyResponseError("No candidates returned: Gemini API returned no candidates")

    first_candidate = candidates[0]
    if not isinstance(first_candidate, dict):
        logger.warning("[Job %s] No candidates returned: Gemini first candidate is not an object: %r", job_id, first_candidate)
        raise GeminiEmptyResponseError("No candidates returned: Gemini API returned a malformed candidate")

    # Extract token usage if available
    usage = payload.get("usageMetadata")
    if usage:
        logger.info("[Job %s] Token usage: prompt=%s, output=%s, thoughts=%s, total=%s",
                     job_id,
                     usage.get("promptTokenCount", "N/A"),
                     usage.get("candidatesTokenCount", "N/A"),
                     usage.get("thoughtsTokenCount", "N/A"),
                     usage.get("totalTokenCount", "N/A"))

    # Log finishReason for observability
    finish_reason = first_candidate.get("finishReason")
    if finish_reason:
        logger.info("[Job %s] Gemini finishReason: %s", job_id, finish_reason)

    # Check finishReason for truncation
    if finish_reason == "MAX_TOKENS":
        logger.warning("[Job %s] Response truncated: Gemini returned MAX_TOKENS (output token limit exceeded). "
                        "Response may be incomplete.", job_id)
        raise GeminiEmptyResponseError(
            "Empty response: Gemini API response was truncated (MAX_TOKENS). "
            "The generated content exceeded the output token limit."
        )

    # Check for safety blocks
    if finish_reason == "SAFETY":
        logger.warning("[Job %s] Response blocked: Gemini returned SAFETY finish reason", job_id)
        raise GeminiEmptyResponseError(
            "Empty response: Gemini API blocked the response due to safety filters."
        )

    content_payload = first_candidate.get("content")
    if not isinstance(content_payload, dict):
        logger.warning("[Job %s] Empty response: Gemini first candidate has no content object: %r", job_id, first_candidate)
        raise GeminiEmptyResponseError("Empty response: Gemini API returned no content")

    parts = content_payload.get("parts")
    if not isinstance(parts, list) or not parts:
        logger.warning("[Job %s] Empty response: Gemini content has no parts array or the array is empty: %r", job_id, content_payload)
        raise GeminiEmptyResponseError("Empty response: Gemini API returned no content parts")

    text_parts: list[str] = []
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            logger.warning("[Job %s] Gemini part %s is not an object: %r", job_id, index, part)
            continue
        text = part.get("text")
        if isinstance(text, str):
            text_parts.append(text)
        else:
            logger.warning("[Job %s] Gemini part %s has no text field: %r", job_id, index, part)

    content = "".join(text_parts)
    if not content.strip():
        logger.warning("[Job %s] Empty response: Gemini API returned an empty response", job_id)
        raise GeminiEmptyResponseError("Empty response: Gemini API returned an empty response")
    logger.info(
        "[Job %s] Raw extracted Gemini text:\n----- BEGIN GEMINI TEXT -----\n%s\n----- END GEMINI TEXT -----",
        job_id,
        content,
    )
    return content.strip()


def _parse_metadata_json(content: str, job_id: str = "unknown") -> dict[str, object]:
    content = _strip_markdown_code_fence(content)
    logger.info(
        "[Job %s] Text passed to json.loads:\n----- BEGIN GEMINI TEXT -----\n%s\n----- END GEMINI TEXT -----",
        job_id,
        content,
    )
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise GeminiInvalidJSONError(
            f"Invalid JSON: Gemini API returned invalid JSON metadata: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise GeminiInvalidJSONError("Invalid JSON: Gemini API returned metadata that is not an object")
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
