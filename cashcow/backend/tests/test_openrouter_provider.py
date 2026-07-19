"""Tests for the OpenRouter metadata provider with model routing."""

import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from io import BytesIO

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ai import openrouter_provider as orp
from app.services.ai.metadata_provider import (
    GeminiAPIError,
    GeminiAuthenticationError,
    GeminiEmptyResponseError,
    GeminiInvalidJSONError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    MetadataGenerationContext,
)
from app.services.ai.openrouter_provider import (
    OPENROUTER_API_BASE,
    OpenRouterMetadataProvider,
    _build_payload,
    _build_prompt,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


class StubResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def _model_in_request(request) -> str | None:
    """Extract the model name from a urllib Request's JSON body."""
    try:
        body = json.loads(request.data.decode("utf-8"))
        return body.get("model")
    except Exception:
        return None


def _make_context(**overrides) -> MetadataGenerationContext:
    kwargs = dict(
        job_id="test-job",
        system_prompt="You are an expert YouTube metadata generator.",
        creative_profile_prompt="Write a clear, searchable title.",
        title_seed="Test Video",
        final_prompt="Generate metadata for Test Video.",
    )
    kwargs.update(overrides)
    return MetadataGenerationContext(**kwargs)


def _valid_openrouter_body(title="Generated Title", description="Generated desc", tags=None):
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "title": title,
                        "description": description,
                        "tags": tags or ["tag1", "tag2"],
                    })
                }
            }
        ]
    }


# ── Param helper to build a provider with injected models & API key ────────────


def _provider(models: list[str] | None = None, api_key: str | None = "sk-or-v1-test") -> OpenRouterMetadataProvider:
    """Build an OpenRouter provider with the given models and API key.

    When ``models`` is ``None``, the default list is used (so the user of this
    helper can pass ``[]`` to test the empty-models branch).
    """
    return OpenRouterMetadataProvider(
        api_key=api_key,
        models=models if models is not None else ["model-a/free", "model-b/free", "model-c/free"],
    )


# ── _build_prompt / _build_payload unit tests ──────────────────────────────────


def test_build_prompt_includes_final_prompt_and_json_instruction():
    context = _make_context(final_prompt="Generate title, description, tags.")
    prompt = _build_prompt(context)
    assert "Generate title, description, tags." in prompt
    assert '"title"' in prompt
    assert "No markdown" in prompt


def test_build_payload_has_expected_structure():
    payload = _build_payload("some-model/free", "my prompt")
    assert payload["model"] == "some-model/free"
    assert payload["messages"][0]["content"] == "my prompt"
    assert payload["response_format"]["type"] == "json_object"
    assert payload["temperature"] == 0.4
    assert payload["max_tokens"] == 8192


# ── Scenario 1: first model succeeds ──────────────────────────────────────────


def test_first_model_succeeds(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        return StubResponse(_valid_openrouter_body(title="First Model OK"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)
    provider = _provider(models=["first/free", "second/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "First Model OK"
    assert len(calls) == 1
    assert _model_in_request(calls[0]) == "first/free"
    assert provider.model == "first/free"


# ── Scenario 2: timeout switches model ────────────────────────────────────────


def test_timeout_switches_model(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if _model_in_request(request) == "first/free":
            raise TimeoutError("timed out")
        return StubResponse(_valid_openrouter_body(title="Second Model OK"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)
    provider = _provider(models=["first/free", "second/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "Second Model OK"
    assert len(calls) == 2
    assert provider.model == "second/free"


# ── Scenario 3: rate limit switches model ─────────────────────────────────────


def test_rate_limit_switches_model(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if _model_in_request(request) == "first/free":
            raise HTTPError(
                url=OPENROUTER_API_BASE,
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=BytesIO(b"rate limited"),
            )
        return StubResponse(_valid_openrouter_body(title="Second After RateLimit"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["first/free", "second/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "Second After RateLimit"
    assert len(calls) == 2
    assert provider.model == "second/free"


# ── Scenario 3b: HTTP 5xx switches model ──────────────────────────────────────


def test_server_error_switches_model(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if _model_in_request(request) == "first/free":
            raise HTTPError(
                url=OPENROUTER_API_BASE,
                code=503,
                msg="Service Unavailable",
                hdrs=None,
                fp=BytesIO(b"service unavailable"),
            )
        return StubResponse(_valid_openrouter_body(title="Second After 503"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["first/free", "second/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "Second After 503"
    assert len(calls) == 2


# ── Scenario 4: invalid JSON retries same model once, then switches ───────────


def test_invalid_json_retries_same_model_once(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if len(calls) == 1:
            return StubResponse({
                "choices": [{"message": {"content": "not valid json"}}]
            })
        return StubResponse(_valid_openrouter_body(title="Model A Retry OK"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["model-a/free", "model-b/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "Model A Retry OK"
    assert len(calls) == 2
    assert all(_model_in_request(c) == "model-a/free" for c in calls)
    assert provider.model == "model-a/free"


def test_invalid_json_retry_exhausted_switches_model(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        return StubResponse({
            "choices": [{"message": {"content": "still not json"}}]
        })

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["model-a/free", "model-b/free"])
    with pytest.raises(GeminiInvalidJSONError):
        provider.generate(_make_context())
    assert len(calls) == 4


# ── Scenario 5: authentication stops immediately ──────────────────────────────


def test_authentication_stops(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        raise HTTPError(
            url=OPENROUTER_API_BASE,
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=BytesIO(b"invalid API key"),
        )

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["model-a/free", "model-b/free"])
    with pytest.raises(GeminiAuthenticationError):
        provider.generate(_make_context())
    # Only the first model was tried
    assert len(calls) == 1


def test_missing_api_key_stops_immediately(monkeypatch):
    from app.core import config as core_config

    monkeypatch.setattr(core_config, "get_config_value", lambda name: None)
    provider = _provider(api_key=None)
    with pytest.raises(GeminiAuthenticationError, match="OPENROUTER_API_KEY is not configured"):
        provider.generate(_make_context())


# ── Scenario 6: all models fail -> last error propagates (fallback handles it) ─


def test_all_models_fail_propagates_last_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            url=OPENROUTER_API_BASE,
            code=429,
            msg="Rate Limited",
            hdrs=None,
            fp=BytesIO(b"rate limit"),
        )

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["model-a/free", "model-b/free"])
    with pytest.raises(GeminiRateLimitError):
        provider.generate(_make_context())


def test_all_models_fail_no_models_configured():
    provider = _provider(models=[])
    with pytest.raises(GeminiAPIError, match="No OpenRouter models"):
        provider.generate(_make_context())


# ── Scenario 7: second model succeeds after first fails ───────────────────────


def test_second_model_succeeds(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if _model_in_request(request) == "first/free":
            raise HTTPError(
                url=OPENROUTER_API_BASE,
                code=503,
                msg="Unavailable",
                hdrs=None,
                fp=BytesIO(b"down"),
            )
        return StubResponse(_valid_openrouter_body(title="Second Model Win"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["first/free", "second/free", "third/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "Second Model Win"
    assert len(calls) == 2  # first failed, second succeeded
    assert provider.model == "second/free"


# ── Scenario 8: third model succeeds after first two fail ─────────────────────


def test_third_model_succeeds(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        model = _model_in_request(request)
        if model == "first/free":
            raise TimeoutError("timeout")
        if model == "second/free":
            raise HTTPError(
                url=OPENROUTER_API_BASE,
                code=429,
                msg="Rate Limited",
                hdrs=None,
                fp=BytesIO(b"rate limit"),
            )
        return StubResponse(_valid_openrouter_body(title="Third Model Win"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["first/free", "second/free", "third/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "Third Model Win"
    assert len(calls) == 3
    assert provider.model == "third/free"


# ── Empty response switches model ─────────────────────────────────────────────


def test_empty_response_switches_model(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if _model_in_request(request) == "first/free":
            return StubResponse({"choices": [{"message": {"content": ""}}]})
        return StubResponse(_valid_openrouter_body(title="Second After Empty"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["first/free", "second/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "Second After Empty"
    assert len(calls) == 2


# ── No choices switches model ─────────────────────────────────────────────────


def test_no_choices_switches_model(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if _model_in_request(request) == "first/free":
            return StubResponse({"choices": []})
        return StubResponse(_valid_openrouter_body(title="Second No Choices"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["first/free", "second/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "Second No Choices"
    assert len(calls) == 2


# ── OpenRouter error object in response switches model ────────────────────────


def test_openrouter_error_object_switches_model(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if _model_in_request(request) == "first/free":
            return StubResponse({
                "error": {"message": "Model overloaded", "code": 503}
            })
        return StubResponse(_valid_openrouter_body(title="Second After Error"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["first/free", "second/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "Second After Error"
    assert len(calls) == 2


# ── Model switching respects configured list order ────────────────────────────


def test_model_switch_logs_and_final_model_set(monkeypatch, caplog):
    caplog.set_level("INFO")

    def fake_urlopen(request, timeout):
        if _model_in_request(request) == "first/free":
            raise TimeoutError("timeout")
        return StubResponse(_valid_openrouter_body(title="OK"))

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["first/free", "second/free"])
    with caplog.at_level("INFO"):
        provider.generate(_make_context())

    assert "OpenRouter switch: model=first/free" in caplog.text
    assert "OpenRouter success: model=second/free" in caplog.text
    assert provider.model == "second/free"


def test_no_models_returns_unknown_model(caplog):
    provider = _provider(models=[])
    assert provider.model == "unknown"


# ── Response with code fence is parsed correctly ──────────────────────────────


def test_code_fence_in_response_is_parsed(monkeypatch):
    def fake_urlopen(request, timeout):
        content = json.dumps({"title": "Fenced Title", "description": "D", "tags": ["t"]})
        fenced = f"```json\n{content}\n```"
        return StubResponse({"choices": [{"message": {"content": fenced}}]})

    monkeypatch.setattr(orp, "urlopen", fake_urlopen)

    provider = _provider(models=["m/free"])
    result = provider.generate(_make_context())
    assert result["title"] == "Fenced Title"


# ── Provider factory integration ──────────────────────────────────────────────


def test_provider_factory_selects_openrouter(monkeypatch):
    from app.services.ai import provider_factory

    monkeypatch.setenv("METADATA_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    provider = provider_factory.get_metadata_provider()
    assert isinstance(provider, OpenRouterMetadataProvider)
    assert provider.name == "openrouter"


def test_provider_factory_openrouter_name(monkeypatch):
    from app.services.ai import provider_factory

    monkeypatch.setenv("METADATA_PROVIDER", "openrouter")
    assert provider_factory.metadata_provider_name() == "OpenRouter"


def test_provider_factory_openrouter_configured(monkeypatch):
    from app.services.ai import provider_factory

    monkeypatch.setenv("METADATA_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    assert provider_factory.metadata_generation_configured() is True


def test_provider_factory_openrouter_not_configured(monkeypatch):
    from app.services.ai import provider_factory

    monkeypatch.setenv("METADATA_PROVIDER", "openrouter")
    monkeypatch.setattr(provider_factory, "get_config_value", lambda name: None)
    assert provider_factory.metadata_generation_configured() is False
