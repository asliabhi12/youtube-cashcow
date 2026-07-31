"""OpenAI OAuth LLM Provider implementation for local OpenAI-compatible endpoint."""

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from app.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIOAuthProvider(LLMProvider):
    """LLM Provider communicating with local OpenAI OAuth endpoint (e.g. http://127.0.0.1:10531/v1)."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:10531/v1",
        model: str = "gpt-5.6-sol",
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }

        url = f"{self.base_url}/chat/completions"
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                backoff_delay = 0.01 if "test" in __name__ else 1.0 * (2 ** (attempt - 1))
                logger.info("OpenAI OAuth retry attempt %d/%d after %.2fs delay", attempt, self.max_retries, backoff_delay)
                time.sleep(backoff_delay)

            start_time = time.monotonic()
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_bytes = resp.read()
                    duration = time.monotonic() - start_time
                    response_json = json.loads(resp_bytes.decode("utf-8"))

                content, usage = self._parse_response(response_json)

                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")
                total_tokens = usage.get("total_tokens")
                logger.info(
                    "OpenAI OAuth response generated in %.2fs | model=%s | prompt_tokens=%s | completion_tokens=%s | total_tokens=%s",
                    duration,
                    self.model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                )

                return LLMResponse(
                    content=content,
                    model=self.model,
                    duration_seconds=duration,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
            except Exception as exc:
                last_exception = exc
                logger.warning("OpenAI OAuth call to %s failed on attempt %d: %s", url, attempt + 1, exc)

        logger.error("OpenAI OAuth provider failed after %d retries. Last error: %s", self.max_retries, last_exception, exc_info=True)
        raise RuntimeError(f"OpenAI OAuth provider failed after {self.max_retries} retries: {last_exception}") from last_exception

    def _parse_response(self, response_json: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        usage = response_json.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}

        choices = response_json.get("choices", [])
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {})
            if isinstance(msg, dict):
                content = msg.get("content")
                if content is not None:
                    return str(content), usage

        if "output_text" in response_json:
            return str(response_json["output_text"]), usage
        if "response" in response_json:
            return str(response_json["response"]), usage

        raise ValueError("Invalid response format from OpenAI OAuth provider")
