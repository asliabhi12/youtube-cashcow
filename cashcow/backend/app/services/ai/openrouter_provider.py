"""OpenRouter-backed YouTube metadata provider with a model router.

Tries a configured list of models in order.  On failure the router either
retries the same model (invalid JSON) or advances to the next model (timeout,
rate limit, server error, empty response) before the MetadataService's own
retry loop ever sees the error.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

from app.services.ai.metadata_provider import (
    GeminiAPIError,
    GeminiAuthenticationError,
    GeminiEmptyResponseError,
    GeminiInvalidJSONError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    MetadataGenerationContext,
    MetadataProvider,
)

logger = logging.getLogger(__name__)

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
REQUEST_TIMEOUT_SECONDS = 60

# Relative path from the provider file to the repo-root settings.yaml.
_SETTINGS_RELATIVE = Path(__file__).resolve().parents[5] / "settings.yaml"


def _load_openrouter_models() -> list[str]:
    """Read the configured model list from ``settings.yaml``."""
    try:
        with open(_SETTINGS_RELATIVE, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        logger.warning("Could not read %s for OpenRouter model config", _SETTINGS_RELATIVE)
        return []
    metadata_cfg = raw.get("metadata") if isinstance(raw, dict) else {}
    models: list[str] | None = metadata_cfg.get("models") if isinstance(metadata_cfg, dict) else None
    if not models:
        logger.warning("No OpenRouter models found under 'metadata.models' in settings.yaml")
        return []
    return models


class OpenRouterMetadataProvider(MetadataProvider):
    """Generate YouTube metadata by routing through a list of OpenRouter models.

    Attributes:
        name: ``"openrouter"``
        model: The model slug that most recently succeeded (or the first model
            if no requests have been made yet).
    """

    name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        models: list[str] | None = None,
    ) -> None:
        from app.core.config import get_config_value

        self._api_key = api_key or get_config_value("OPENROUTER_API_KEY")
        self._models = models if models is not None else _load_openrouter_models()
        self.model = self._models[0] if self._models else "unknown"

    # ── Public interface ──────────────────────────────────────────────────────

    def generate(self, context: MetadataGenerationContext) -> dict[str, object]:
        job_id = context.job_id or "unknown"

        if not self._api_key:
            logger.error("[Job %s] OpenRouter authentication error: OPENROUTER_API_KEY is not configured", job_id)
            raise GeminiAuthenticationError("OPENROUTER_API_KEY is not configured")

        if not self._models:
            logger.error("[Job %s] No OpenRouter models are configured", job_id)
            raise GeminiAPIError("No OpenRouter models configured in settings.yaml")

        prompt = _build_prompt(context)
        last_error: Exception | None = None
        index = 0

        while index < len(self._models):
            current_model = self._models[index]
            logger.info("[Job %s] OpenRouter switch: model=%s", job_id, current_model)

            # ── First attempt for this model ──────────────────────────────
            try:
                result = self._call_model(current_model, prompt, job_id)
                self.model = current_model
                logger.info(
                    "[Job %s] OpenRouter success: model=%s final_model=%s",
                    job_id, current_model, self.model,
                )
                return result
            except GeminiInvalidJSONError as exc:
                # Retry the same model once.
                logger.warning(
                    "[Job %s] OpenRouter failure: model=%s reason=invalid_json retry=1",
                    job_id, current_model,
                )
                try:
                    result = self._call_model(current_model, prompt, job_id)
                    self.model = current_model
                    logger.info(
                        "[Job %s] OpenRouter success: model=%s final_model=%s",
                        job_id, current_model, self.model,
                    )
                    return result
                except GeminiInvalidJSONError as exc2:
                    last_error = exc2
                    logger.warning(
                        "[Job %s] OpenRouter switch: model=%s reason=invalid_json_retry_exhausted",
                        job_id, current_model,
                    )
                    index += 1
                    continue
            except GeminiAuthenticationError:
                logger.error(
                    "[Job %s] OpenRouter failure: model=%s reason=auth_failed stop=true",
                    job_id, current_model,
                )
                raise
            except (GeminiTimeoutError, GeminiRateLimitError, GeminiAPIError, GeminiEmptyResponseError) as exc:
                last_error = exc
                reason = type(exc).__name__.replace("Gemini", "").replace("Error", "").lower()
                logger.warning(
                    "[Job %s] OpenRouter switch: model=%s reason=%s",
                    job_id, current_model, reason,
                )
                index += 1
                continue

        # All models exhausted.
        logger.error(
            "[Job %s] OpenRouter failure: all_models_exhausted count=%d final_model=%s",
            job_id, len(self._models), self.model,
        )
        raise last_error or GeminiAPIError("All OpenRouter models failed")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _call_model(
        self, model: str, prompt: str, job_id: str,
    ) -> dict[str, object]:
        """Call one OpenRouter model and return parsed metadata JSON."""
        import os

        start = time.monotonic()
        payload = _build_payload(model, prompt)
        body_bytes = json.dumps(payload).encode("utf-8")

        request = Request(
            f"{OPENROUTER_API_BASE}/chat/completions",
            data=body_bytes,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "http://localhost:8000"),
                "X-Title": os.getenv("OPENROUTER_APP_TITLE", "YouTube CashCow"),
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                response_body = response.read().decode("utf-8")
                duration = time.monotonic() - start
                logger.info(
                    "[Job %s] OpenRouter response: model=%s status=200 duration=%.2fs",
                    job_id, model, duration,
                )
                logger.info("[Job %s] OpenRouter raw response: %s", job_id, response_body)
        except HTTPError as exc:
            duration = time.monotonic() - start
            detail = _read_error_body(exc)
            logger.info(
                "[Job %s] OpenRouter response: model=%s status=%s duration=%.2fs",
                job_id, model, exc.code, duration,
            )
            logger.info("[Job %s] OpenRouter raw response: %s", job_id, detail)

            if exc.code in (401, 403):
                raise GeminiAuthenticationError(
                    f"OpenRouter authentication failed: HTTP {exc.code}: {detail or exc.reason}"
                ) from exc
            if exc.code == 429:
                raise GeminiRateLimitError(
                    f"OpenRouter rate limit: HTTP {exc.code}: {detail or exc.reason}"
                ) from exc
            if exc.code == 402:
                raise GeminiAPIError(
                    f"OpenRouter insufficient credits: HTTP {exc.code}: {detail or exc.reason}"
                ) from exc
            if 500 <= exc.code < 600:
                raise GeminiAPIError(
                    f"OpenRouter server error: HTTP {exc.code}: {detail or exc.reason}"
                ) from exc
            raise GeminiAPIError(
                f"OpenRouter API error: HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except (TimeoutError, URLError) as exc:
            duration = time.monotonic() - start
            logger.info(
                "[Job %s] OpenRouter response: model=%s status=timeout duration=%.2fs",
                job_id, model, duration,
            )
            if isinstance(exc, TimeoutError):
                raise GeminiTimeoutError(
                    f"OpenRouter request timed out after {REQUEST_TIMEOUT_SECONDS}s"
                ) from exc
            raise GeminiAPIError(f"OpenRouter request failed: {exc}") from exc

        return _extract_and_parse(response_body, job_id, model)

    def __repr__(self) -> str:
        return f"OpenRouterMetadataProvider(models={self._models}, model={self.model})"


# ── Module-level helpers ──────────────────────────────────────────────────────


def _build_prompt(context: MetadataGenerationContext) -> str:
    return "\n\n".join(
        [
            context.final_prompt,
            "Return ONLY valid JSON in this exact format:",
            '{\n  "title": "...",\n  "description": "...",\n  "tags": ["...", "...", "..."]\n}',
            "No markdown. No code fences. No explanations.",
        ]
    )


def _build_payload(model: str, prompt: str) -> dict[str, object]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.4,
        "max_tokens": 8192,
    }


def _extract_and_parse(response_body: str, job_id: str, model: str) -> dict[str, object]:
    """Extract the assistant message content from an OpenAI-style response."""
    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError as exc:
        logger.warning(
            "[Job %s] OpenRouter response is not valid JSON: %s", job_id, exc,
        )
        raise GeminiInvalidJSONError(
            f"OpenRouter returned malformed JSON: {exc}"
        ) from exc

    # Check for OpenRouter-level error objects.
    error_obj = payload.get("error")
    if error_obj:
        err_msg = error_obj.get("message", str(error_obj))
        logger.warning(
            "[Job %s] OpenRouter returned an error: %s", job_id, err_msg,
        )
        raise GeminiAPIError(f"OpenRouter error: {err_msg}")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        logger.warning(
            "[Job %s] OpenRouter response has no choices: %s", job_id, response_body,
        )
        raise GeminiEmptyResponseError("OpenRouter returned no choices")

    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else {}
    content = message.get("content") if isinstance(message, dict) else None

    if not isinstance(content, str) or not content.strip():
        logger.warning(
            "[Job %s] OpenRouter response has no message content: %s",
            job_id, response_body,
        )
        raise GeminiEmptyResponseError("OpenRouter returned an empty response")

    # Log finish_reason if present.
    finish_reason = first.get("finish_reason")
    if finish_reason:
        logger.info(
            "[Job %s] OpenRouter finish_reason: %s (model=%s)", job_id, finish_reason, model,
        )

    logger.info(
        "[Job %s] OpenRouter extracted text:\n----- BEGIN TEXT -----\n%s\n----- END TEXT -----",
        job_id, content,
    )

    return _parse_json_content(content, job_id)


def _parse_json_content(content: str, job_id: str) -> dict[str, object]:
    """Parse the model's JSON response, handling markdown code fences."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        opening = lines[0].strip().lower()
        if opening in {"```", "```json"} and len(lines) > 1 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()

    logger.info(
        "[Job %s] Text passed to json.loads:\n----- BEGIN TEXT -----\n%s\n----- END TEXT -----",
        job_id, text,
    )
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiInvalidJSONError(
            f"OpenRouter returned invalid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise GeminiInvalidJSONError("OpenRouter returned metadata that is not a JSON object")
    return parsed


def _read_error_body(exc: HTTPError) -> str:
    try:
        return exc.read().decode("utf-8").strip()
    except Exception:  # noqa: BLE001
        return ""
