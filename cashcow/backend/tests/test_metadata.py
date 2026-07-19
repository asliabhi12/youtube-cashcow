"""Unit and API tests for Phase 9A1 metadata."""

import json
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app import main as main_module
from app.models.metadata import MetadataCreate, MetadataFields, MetadataUpdate
from app.api import jobs as jobs_api
from app.services import metadata as metadata_module
from app.services.ai import gemini_provider
from app.services.ai.gemini_provider import GeminiMetadataProvider
from app.services.ai.metadata_provider import GeminiInvalidJSONError, GeminiRateLimitError
from app.services.ai.mock_provider import MockMetadataProvider
from app.services.ai import provider_factory
from app.services.ai.provider_factory import get_metadata_provider
from app.services.jobs import job_store
from app.services.metadata import metadata_service
from app.services import workflow as workflow_module
from app.services.youtube_upload import YouTubeUploadResult


@pytest.fixture(autouse=True)
def mock_metadata_provider(monkeypatch):
    monkeypatch.setattr(
        metadata_module,
        "get_metadata_provider",
        lambda: MockMetadataProvider(),
    )


@pytest.fixture
def job():
    created = job_store.create("https://youtube.example/watch?v=abc")
    yield created
    metadata_service.delete(created.id)
    job_store.delete(created.id)


def _fake_successful_upload(job_id, progress, log):
    uploaded_at = metadata_module.datetime.now(metadata_module.timezone.utc)
    job_store.set_upload_started(job_id)
    job_store.set_upload_result(
        job_id,
        "uploaded",
        video_id="yt123",
        video_url="https://www.youtube.com/watch?v=yt123",
        uploaded_at=uploaded_at,
    )
    return YouTubeUploadResult(
        video_id="yt123",
        video_url="https://www.youtube.com/watch?v=yt123",
        uploaded_at=uploaded_at,
        privacy_status="private",
    )


def test_metadata_model_enforces_youtube_limits():
    with pytest.raises(ValidationError):
        MetadataFields(title="x" * 101)
    with pytest.raises(ValidationError):
        MetadataFields(title="x", description="x" * 5_001)
    with pytest.raises(ValidationError):
        MetadataFields(title="x", tags=["x" * 501])
    with pytest.raises(ValidationError):
        MetadataFields(title="x", hashtags=[f"#{n}" for n in range(16)])


def test_hashtags_are_normalized():
    data = MetadataCreate(title=" Title ", tags=["news", " News "], hashtags=["news", "#video"])
    assert data.title == "Title"
    assert data.tags == ["news"]
    assert data.hashtags == ["#news", "#video"]


def test_generation_handles_long_title_seeds():
    job = job_store.create("https://youtube.example/watch?v=" + ("x" * 200))
    try:
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="x" * 100))
        assert metadata is not None
        assert len(metadata.title) == 100
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)


def test_generation_update_and_regeneration(job):
    first = metadata_service.generate(job.id)
    assert first is not None
    assert first.job_id == job.id
    assert first.provider == "mock"
    assert job_store.get(job.id).has_metadata is True
    assert job_store.get(job.id).metadata_status == "available"

    updated = metadata_service.update(job.id, MetadataUpdate(title="Edited"))
    assert updated.title == "Edited"
    regenerated = metadata_service.regenerate(job.id)
    assert regenerated is not None
    assert regenerated.title != "Edited"
    assert regenerated.generated_at >= first.generated_at


def test_generation_sends_profile_prompt_title_seed_and_context(monkeypatch):
    captured = {}

    class CaptureProvider:
        name = "capture"
        model = "capture-v1"

        def generate(self, context):
            captured["context"] = context
            return {
                "title": "Generated title",
                "description": "Generated description",
                "tags": ["generated", "metadata"],
            }

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: CaptureProvider())
    job = job_store.create(
        "https://youtube.example/watch?v=context",
        profile_id="cinematic",
    )
    job_store.set_output_name(job.id, "Original_Video_Title.mp4")
    try:
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="My Intent"))
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)

    context = captured["context"]
    assert metadata is not None
    assert metadata.title == "Generated title"
    assert context.title_seed == "My Intent"
    assert context.creative_profile_prompt.startswith("Write a cinematic")
    assert context.original_title == "Original Video Title"
    assert context.output_filename == "Original_Video_Title.mp4"
    assert "Title Seed: My Intent" in context.final_prompt
    assert "Original YouTube title: Original Video Title" in context.final_prompt
    assert "Return ONLY a valid JSON object" in context.final_prompt


def test_generation_uses_persisted_job_title_seed_when_request_is_empty(monkeypatch):
    captured = {}

    class CaptureProvider:
        name = "capture"
        model = "capture-v1"

        def generate(self, context):
            captured["context"] = context
            return {
                "title": "Mumbai ride",
                "description": "Generated from the persisted seed.",
                "tags": ["mumbai", "ride"],
            }

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: CaptureProvider())
    job = job_store.create(
        "https://youtube.example/watch?v=seeded",
        title_seed="Epic Ride Through Mumbai",
    )
    job_store.set_output_name(job.id, "Original Video.mp4")
    try:
        metadata = metadata_service.generate(job.id)
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)

    context = captured["context"]
    assert metadata is not None
    assert context.title_seed == "Epic Ride Through Mumbai"
    assert "Title Seed: Epic Ride Through Mumbai" in context.final_prompt
    assert "Original YouTube title: Original Video" in context.final_prompt


def test_metadata_routes_create_get_update_and_regenerate(job):
    client = TestClient(app)
    response = client.post(f"/jobs/{job.id}/metadata", json={"title": "API title"})
    assert response.status_code == 201
    assert response.json()["title"].startswith("API title")

    response = client.get(f"/jobs/{job.id}/metadata")
    assert response.status_code == 200
    response = client.put(f"/jobs/{job.id}/metadata", json={"description": "Updated"})
    assert response.status_code == 200
    assert response.json()["description"] == "Updated"
    response = client.post(f"/jobs/{job.id}/metadata/regenerate")
    assert response.status_code == 200
    assert response.json()["provider"] == "mock"


def test_metadata_routes_distinguish_missing_job_and_metadata():
    client = TestClient(app)
    assert client.get("/jobs/missing/metadata").status_code == 404
    job = job_store.create("https://youtube.example/watch?v=missing")
    try:
        assert client.get(f"/jobs/{job.id}/metadata").status_code == 404
        assert client.put(f"/jobs/{job.id}/metadata", json={"title": "x"}).status_code == 404
    finally:
        job_store.delete(job.id)


def test_create_job_receives_and_persists_title_seed(monkeypatch):
    submitted = {}

    def fake_submit(job_id, url, **kwargs):
        submitted["job_id"] = job_id
        submitted.update(kwargs)

    monkeypatch.setattr(jobs_api.job_queue, "submit", fake_submit)
    monkeypatch.setattr(jobs_api.app_settings, "set_last_profile", lambda profile_id: None)
    client = TestClient(app)
    response = client.post(
        "/jobs",
        json={
            "url": "https://youtube.example/watch?v=create-seed",
            "profile_id": "custom",
            "export_quality": "balanced",
            "title_seed": "Epic Ride Through Mumbai",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    try:
        assert payload["title_seed"] == "Epic Ride Through Mumbai"
        stored = job_store.get(payload["id"])
        assert stored is not None
        assert stored.title_seed == "Epic Ride Through Mumbai"
        assert submitted["job_id"] == payload["id"]
    finally:
        job_store.delete(payload["id"])


class StubResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def _gemini_api_payload(content):
    return {"candidates": [{"content": {"parts": [{"text": content}]}}]}


def test_provider_factory_selects_gemini_and_mock(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert isinstance(get_metadata_provider(), GeminiMetadataProvider)
    assert isinstance(get_metadata_provider("gemini"), GeminiMetadataProvider)
    assert isinstance(get_metadata_provider("mock"), MockMetadataProvider)


def _valid_gemini_metadata_json() -> str:
    return json.dumps(
        {
            "title": "Gemini title",
            "description": "Gemini description",
            "tags": ["gemini", "metadata"],
        }
    )


def test_gemini_metadata_generation_success(monkeypatch, caplog, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")

    def fake_urlopen(request, timeout):
        assert timeout == gemini_provider.REQUEST_TIMEOUT_SECONDS
        assert request.full_url.endswith("/models/gemini-test:generateContent")
        assert request.headers["X-goog-api-key"] == "test-key"
        payload = json.loads(request.data.decode("utf-8"))
        prompt = payload["contents"][0]["parts"][0]["text"]
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert "Return ONLY valid JSON" in prompt
        return StubResponse(_gemini_api_payload(_valid_gemini_metadata_json()))

    monkeypatch.setattr(gemini_provider, "urlopen", fake_urlopen)
    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Seed"))

    assert metadata is not None
    assert metadata.provider == "gemini"
    assert metadata.model == "gemini-test"
    assert metadata.title == "Gemini title"
    assert metadata.description == "Gemini description"
    assert metadata.tags == ["gemini", "metadata"]
    assert "Complete Gemini HTTP response body:" in caplog.text
    assert "Raw extracted Gemini text:" in caplog.text
    assert "----- BEGIN GEMINI TEXT -----" in caplog.text
    assert "Gemini title" in caplog.text
    assert "----- END GEMINI TEXT -----" in caplog.text


@pytest.mark.parametrize(
    "content",
    [
        _valid_gemini_metadata_json(),
        f"```json\n{_valid_gemini_metadata_json()}\n```",
        f"\n\n  {_valid_gemini_metadata_json()}  \n",
    ],
)
def test_gemini_parses_plain_fenced_and_whitespace_json(monkeypatch, job, content):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        gemini_provider,
        "urlopen",
        lambda request, timeout: StubResponse(_gemini_api_payload(content)),
    )

    metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Seed"))

    assert metadata is not None
    assert metadata.title == "Gemini title"
    assert metadata.description == "Gemini description"
    assert metadata.tags == ["gemini", "metadata"]


def test_gemini_malformed_json_leaves_metadata_unavailable(monkeypatch, caplog, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        gemini_provider,
        "urlopen",
        lambda request, timeout: StubResponse(_gemini_api_payload("```json\nnot json\n```")),
    )

    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id)

    assert metadata is None
    assert job_store.get(job.id).has_metadata is False
    assert job_store.get(job.id).metadata_status == "unavailable"
    assert "Metadata provider error" in caplog.text
    assert "Raw extracted Gemini text:" in caplog.text
    assert "----- BEGIN GEMINI TEXT -----" in caplog.text
    assert "not json" in caplog.text
    assert "----- END GEMINI TEXT -----" in caplog.text


@pytest.mark.parametrize(
    ("payload", "expected_log"),
    [
        ({}, "Gemini response has no candidates array or the array is empty"),
        ({"candidates": []}, "Gemini response has no candidates array or the array is empty"),
        ({"candidates": [{}]}, "Gemini first candidate has no content object"),
        (
            {"candidates": [{"content": {"parts": []}}]},
            "Gemini content has no parts array or the array is empty",
        ),
        (
            {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "text/plain"}}]}}]},
            "Gemini part 0 has no text field",
        ),
    ],
)
def test_gemini_logs_missing_candidate_or_text_reason(monkeypatch, caplog, job, payload, expected_log):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        gemini_provider,
        "urlopen",
        lambda request, timeout: StubResponse(payload),
    )

    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id)

    assert metadata is None
    assert job_store.get(job.id).metadata_status == "unavailable"
    assert "Complete Gemini HTTP response body:" in caplog.text
    assert expected_log in caplog.text


def test_gemini_max_tokens_truncation_leaves_metadata_unavailable(monkeypatch, caplog, job):
    """MAX_TOKENS finish reason should be caught as MAX_TOKENS truncation."""
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    truncated_json = '{"title": "Partial", "description": "Truncated'
    truncated_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": truncated_json}],
                },
                "finishReason": "MAX_TOKENS",
            }
        ],
    }

    monkeypatch.setattr(
        gemini_provider,
        "urlopen",
        lambda request, timeout: StubResponse(truncated_payload),
    )

    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id)

    assert metadata is None
    assert job_store.get(job.id).metadata_status == "unavailable"
    assert "MAX_TOKENS" in caplog.text
    assert "truncated" in caplog.text


def test_gemini_missing_api_key_leaves_metadata_unavailable(monkeypatch, caplog, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(gemini_provider, "get_config_value", lambda name: None)

    metadata = metadata_service.generate(job.id)

    assert metadata is None
    assert job_store.get(job.id).has_metadata is False
    assert job_store.get(job.id).metadata_status == "unavailable"
    assert "GEMINI_API_KEY is not configured" in caplog.text


def test_gemini_api_error_leaves_metadata_unavailable(monkeypatch, caplog, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake_urlopen(request, timeout):
        raise HTTPError(
            url=gemini_provider.GEMINI_API_BASE_URL,
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=BytesIO(b"rate limited"),
        )

    monkeypatch.setattr(gemini_provider, "urlopen", fake_urlopen)
    metadata = metadata_service.generate(job.id)

    assert metadata is None
    assert job_store.get(job.id).has_metadata is False
    assert job_store.get(job.id).metadata_status == "unavailable"
    assert "Gemini API error 429" in caplog.text


def test_metadata_response_validation_leaves_metadata_unavailable(monkeypatch, caplog, job):
    class BadProvider:
        name = "bad"
        model = "bad-v1"

        def generate(self, context):
            return {"title": "", "description": "", "tags": "not a list"}

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: BadProvider())

    metadata = metadata_service.generate(job.id)

    assert metadata is None
    assert job_store.get(job.id).has_metadata is False
    assert job_store.get(job.id).metadata_status == "unavailable"
    assert "Schema validation failure" in caplog.text


def test_startup_logs_provider_with_api_key(monkeypatch, caplog):
    monkeypatch.setattr(main_module, "metadata_generation_configured", lambda: True)

    with caplog.at_level("INFO"):
        with TestClient(app):
            pass

    assert "AI metadata provider active: Gemini" in caplog.text
    assert "AI metadata generation is disabled" not in caplog.text


def test_startup_warns_without_api_key(monkeypatch, caplog):
    monkeypatch.setattr(main_module, "metadata_generation_configured", lambda: False)

    with caplog.at_level("INFO"):
        with TestClient(app):
            pass

    assert "AI metadata provider active: Gemini" in caplog.text
    assert "GEMINI_API_KEY is not configured; AI metadata generation is disabled." in caplog.text


def test_workflow_auto_generates_metadata_after_success(monkeypatch):
    class FakeRunner:
        def __init__(self, settings, registry, downloader, progress):
            self.progress = progress

        def run(self, workflow):
            return SimpleNamespace(output_file=Path("/tmp/output.mp4"))

    monkeypatch.setattr(workflow_module, "PipelineRunner", FakeRunner)
    monkeypatch.setattr(workflow_module, "default_registry", lambda: object())
    monkeypatch.setattr(workflow_module, "HardenedDownloader", lambda settings: object())
    monkeypatch.setattr(
        workflow_module.youtube_upload_service,
        "upload_job",
        _fake_successful_upload,
    )

    job = job_store.create("https://youtube.example/watch?v=auto")
    try:
        workflow_module._execute(job.id, object(), object())

        latest = job_store.get(job.id)
        assert latest is not None
        assert latest.status == "completed"
        assert latest.has_metadata is True
        assert latest.metadata_status == "available"
        assert latest.youtube_upload_status == "uploaded"
        assert latest.youtube_video_id == "yt123"
        metadata = metadata_service.get(job.id)
        assert metadata is not None
        assert metadata.title
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)


def test_workflow_metadata_failure_does_not_fail_completed_job(monkeypatch):
    class FakeRunner:
        def __init__(self, settings, registry, downloader, progress):
            self.progress = progress

        def run(self, workflow):
            return SimpleNamespace(output_file=Path("/tmp/output.mp4"))

    monkeypatch.setattr(workflow_module, "PipelineRunner", FakeRunner)
    monkeypatch.setattr(workflow_module, "default_registry", lambda: object())
    monkeypatch.setattr(workflow_module, "HardenedDownloader", lambda settings: object())
    monkeypatch.setattr(workflow_module.metadata_service, "generate", lambda job_id, *args, **kwargs: None)
    monkeypatch.setattr(
        workflow_module.youtube_upload_service,
        "upload_job",
        _fake_successful_upload,
    )

    job = job_store.create("https://youtube.example/watch?v=auto-fail")
    try:
        workflow_module._execute(job.id, object(), object())

        latest = job_store.get(job.id)
        assert latest is not None
        assert latest.status == "completed"
        assert latest.has_metadata is True
        assert latest.metadata_status == "available"
        assert metadata_service.get(job.id) is not None
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)


def test_metadata_retrieval_after_automatic_generation(monkeypatch):
    class FakeRunner:
        def __init__(self, settings, registry, downloader, progress):
            self.progress = progress

        def run(self, workflow):
            return SimpleNamespace(output_file=Path("/tmp/output.mp4"))

    monkeypatch.setattr(workflow_module, "PipelineRunner", FakeRunner)
    monkeypatch.setattr(workflow_module, "default_registry", lambda: object())
    monkeypatch.setattr(workflow_module, "HardenedDownloader", lambda settings: object())
    monkeypatch.setattr(
        workflow_module.youtube_upload_service,
        "upload_job",
        _fake_successful_upload,
    )

    client = TestClient(app)
    job = job_store.create("https://youtube.example/watch?v=auto-get")
    try:
        workflow_module._execute(job.id, object(), object())

        response = client.get(f"/jobs/{job.id}/metadata")
        assert response.status_code == 200
        assert response.json()["title"]
        assert response.json()["tags"]
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)


# ── Language handling ──────────────────────────────────────────────────────────


def test_system_prompt_has_language_instructions():
    """The system prompt must include English/Hindi/Hinglish handling rules."""
    prompt = metadata_module.SYSTEM_PROMPT
    assert "Hindi" in prompt
    assert "Hinglish" in prompt
    assert "English" in prompt
    assert "Do NOT translate to English" in prompt


def test_english_title_seed_generates_metadata(monkeypatch):
    captured = {}

    class CaptureProvider:
        name = "capture"
        model = "capture-v1"

        def generate(self, context):
            captured["context"] = context
            return {
                "title": "Top 10 Mumbai Street Food Spots",
                "description": "Exploring the best street food in Mumbai.",
                "tags": ["mumbai", "street food", "india"],
            }

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: CaptureProvider())
    job = job_store.create("https://youtube.example/watch?v=eng")
    job_store.set_output_name(job.id, "Mumbai_Street_Food.mp4")
    try:
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Best Street Food in Mumbai"))
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)

    assert metadata is not None
    assert metadata.title == "Top 10 Mumbai Street Food Spots"
    ctx = captured["context"]
    assert ctx.title_seed == "Best Street Food in Mumbai"
    assert "English" in ctx.system_prompt
    assert "Hinglish" in ctx.system_prompt
    assert "Hindi" in ctx.system_prompt


def test_hindi_title_seed_preserves_language(monkeypatch):
    captured = {}

    class CaptureProvider:
        name = "capture"
        model = "capture-v1"

        def generate(self, context):
            captured["context"] = context
            return {
                "title": "मुंबई की गलियों का स्वाद",
                "description": "मुंबई के स्ट्रीट फूड की एक रोमांचक यात्रा।",
                "tags": ["मुंबई", "स्ट्रीट फूड"],
            }

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: CaptureProvider())
    job = job_store.create("https://youtube.example/watch?v=hindi")
    job_store.set_output_name(job.id, "Mumbai_Food.mp4")
    try:
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="मुंबई की गलियों का स्वाद"))
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)

    assert metadata is not None
    assert "मुंबई" in metadata.title
    assert "स्वाद" in metadata.title
    ctx = captured["context"]
    assert ctx.title_seed == "मुंबई की गलियों का स्वाद"


def test_hinglish_title_seed_preserves_mixed_language(monkeypatch):
    captured = {}

    class CaptureProvider:
        name = "capture"
        model = "capture-v1"

        def generate(self, context):
            captured["context"] = context
            return {
                "title": "Mumbai ki Galiyon ka Swaad - Street Food Tour",
                "description": "Exploring Mumbai ke best street food spots!",
                "tags": ["mumbai", "street food", "hinglish"],
            }

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: CaptureProvider())
    job = job_store.create("https://youtube.example/watch?v=hinglish")
    job_store.set_output_name(job.id, "Mumbai_Food.mp4")
    try:
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Mumbai ki galiyon ka swaad - street food tour"))
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)

    assert metadata is not None
    assert "Mumbai" in metadata.title
    assert "galiyon" in metadata.title or "Galiyon" in metadata.title
    assert "Street Food" in metadata.title or "street food" in metadata.title
    ctx = captured["context"]
    assert ctx.title_seed == "Mumbai ki galiyon ka swaad - street food tour"


def test_unicode_tags_are_preserved(monkeypatch):
    class UnicodeProvider:
        name = "unicode"
        model = "unicode-v1"

        def generate(self, context):
            return {
                "title": "Unicode Test 🎬",
                "description": "Testing emoji and non-Latin characters: こんにちは",
                "tags": ["emoji 🎉", "日本語", "हिन्दी", "unicode"],
            }

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: UnicodeProvider())
    job = job_store.create("https://youtube.example/watch?v=unicode")
    try:
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Unicode Test"))
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)

    assert metadata is not None
    assert "🎬" in metadata.title
    assert "こんにちは" in metadata.description
    assert "日本語" in metadata.tags
    assert "हिन्दी" in metadata.tags


# ── Retry logic ────────────────────────────────────────────────────────────────


def test_retry_succeeds_after_transient_failure(monkeypatch, job):
    call_count = 0

    class RetryThenSuccessProvider:
        name = "retry"
        model = "retry-v1"

        def generate(self, context):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise GeminiRateLimitError("Rate limited: too many requests")
            return {
                "title": "Retry Success Title",
                "description": "Generated on second attempt",
                "tags": ["retry", "success"],
            }

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: RetryThenSuccessProvider())
    metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Retry Test"))

    assert metadata is not None
    assert metadata.title == "Retry Success Title"
    assert call_count == 2


def test_retry_exhaustion_triggers_fallback(monkeypatch, caplog, job):
    call_count = 0

    class AlwaysFailsProvider:
        name = "failing"
        model = "failing-v1"

        def generate(self, context):
            nonlocal call_count
            call_count += 1
            raise GeminiInvalidJSONError("Invalid JSON: always fails")

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: AlwaysFailsProvider())

    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id, fallback=True)

    assert metadata is not None
    assert metadata.provider == "fallback"
    assert call_count == 3
    assert "FALLBACK_METADATA" in caplog.text
    assert "METADATA_FAILED" in caplog.text


def test_retry_exhaustion_returns_none_without_fallback(monkeypatch, job):
    class AlwaysFailsProvider:
        name = "failing"
        model = "failing-v1"

        def generate(self, context):
            raise GeminiInvalidJSONError("Invalid JSON: always fails")

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: AlwaysFailsProvider())

    metadata = metadata_service.generate(job.id, fallback=False)

    assert metadata is None
    assert job_store.get(job.id).metadata_status == "unavailable"


# ── Timeout handling ───────────────────────────────────────────────────────────


def test_timeout_error_is_caught_and_logged(monkeypatch, caplog, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake_timeout(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(gemini_provider, "urlopen", fake_timeout)

    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id)

    assert metadata is None
    assert job_store.get(job.id).metadata_status == "unavailable"
    assert "Timeout" in caplog.text


# ── Token usage logging ────────────────────────────────────────────────────────


def test_token_usage_is_logged(monkeypatch, caplog, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake_urlopen(request, timeout):
        response_body = json.dumps({
            "candidates": [{"content": {"parts": [{"text": json.dumps({"title": "T", "description": "D", "tags": ["t"]})}]}}],
            "usageMetadata": {
                "promptTokenCount": 42,
                "candidatesTokenCount": 17,
                "thoughtsTokenCount": 10,
                "totalTokenCount": 69,
            },
        })
        return StubResponse(json.loads(response_body))

    monkeypatch.setattr(gemini_provider, "urlopen", fake_urlopen)

    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Token Test"))

    assert metadata is not None
    assert "Token usage:" in caplog.text
    assert "prompt=42" in caplog.text
    assert "output=17" in caplog.text


# ── Workflow transitions ───────────────────────────────────────────────────────


def test_workflow_transitions_metadata_ready(monkeypatch, caplog, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake_urlopen(request, timeout):
        return StubResponse({
            "candidates": [{"content": {"parts": [{"text": json.dumps({"title": "Ready Title", "description": "Ready desc", "tags": ["ready"]})}]}}]
        })

    monkeypatch.setattr(gemini_provider, "urlopen", fake_urlopen)

    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Ready"))

    assert metadata is not None
    assert "METADATA_READY" in caplog.text
    assert "GENERATING_METADATA" in caplog.text
    assert "Database write result: Successfully stored metadata" in caplog.text


def test_workflow_transitions_metadata_failed_and_fallback(monkeypatch, caplog, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake_urlopen(request, timeout):
        raise HTTPError(
            url=gemini_provider.GEMINI_API_BASE_URL,
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=BytesIO(b"rate limited"),
        )

    monkeypatch.setattr(gemini_provider, "urlopen", fake_urlopen)

    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id, fallback=True)

    assert metadata is not None
    assert metadata.provider == "fallback"
    assert "METADATA_FAILED" in caplog.text
    assert "FALLBACK_METADATA" in caplog.text
    assert job_store.get(job.id).metadata_status == "available"


def test_retry_workflow_transition(monkeypatch, caplog, job):
    call_count = 0

    class RetryProvider:
        name = "retry"
        model = "retry-v1"

        def generate(self, context):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise GeminiInvalidJSONError("Invalid JSON")
            return {"title": "Retry OK", "description": "Retry desc", "tags": ["retry"]}

    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: RetryProvider())

    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Retry"))

    assert metadata is not None
    assert "RETRYING_METADATA" in caplog.text
    assert "METADATA_READY" in caplog.text


# ── Fallback edge cases ────────────────────────────────────────────────────────


def test_fallback_uses_title_seed_when_available(monkeypatch, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_provider, "urlopen", lambda req, timeout: (_ for _ in ()).throw(
        HTTPError(url="", code=500, msg="Error", hdrs=None, fp=BytesIO(b""))
    ))

    metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Fallback Test Title"), fallback=True)
    assert metadata is not None
    assert metadata.provider == "fallback"
    assert metadata.title == "Fallback Test Title"
    assert metadata.description == ""
    assert metadata.tags == []


def test_fallback_uses_original_title_when_no_seed(monkeypatch, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_provider, "urlopen", lambda req, timeout: (_ for _ in ()).throw(
        HTTPError(url="", code=500, msg="Error", hdrs=None, fp=BytesIO(b""))
    ))
    job_store.set_output_name(job.id, "Original_Video_Title.mp4")

    metadata = metadata_service.generate(job.id, fallback=True)
    assert metadata is not None
    assert metadata.provider == "fallback"
    assert metadata.title == "Original Video Title"


def test_fallback_uses_output_name_when_no_seed_or_title(monkeypatch, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_provider, "urlopen", lambda req, timeout: (_ for _ in ()).throw(
        HTTPError(url="", code=500, msg="Error", hdrs=None, fp=BytesIO(b""))
    ))
    job_store.set_output_name(job.id, "Some_Video_Name.mp4")

    metadata = metadata_service.generate(job.id, fallback=True)
    assert metadata is not None
    assert metadata.provider == "fallback"
    assert "Some Video Name" in metadata.title


# ── Provider request logging ───────────────────────────────────────────────────


def test_job_id_is_included_in_provider_logs(monkeypatch, caplog, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", provider_factory.get_metadata_provider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake_urlopen(request, timeout):
        return StubResponse({
            "candidates": [{"content": {"parts": [{"text": json.dumps({"title": "T", "description": "D", "tags": ["t"]})}]}}]
        })

    monkeypatch.setattr(gemini_provider, "urlopen", fake_urlopen)

    with caplog.at_level("INFO"):
        metadata = metadata_service.generate(job.id, MetadataCreate(title_seed="Log Test"))

    assert metadata is not None
    assert f"[Job {job.id}]" in caplog.text


# ── Transcript extraction ───────────────────────────────────────────────────────


def test_extract_transcript_text_returns_none_for_empty_paths():
    assert metadata_module._extract_transcript_text([]) is None


def test_extract_transcript_text_returns_none_for_missing_files():
    assert metadata_module._extract_transcript_text(["/tmp/nonexistent.vtt"]) is None


def test_extract_transcript_text_strips_vtt_formatting(tmp_path):
    vtt_file = tmp_path / "test.en.vtt"
    vtt_file.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:04.000\n"
        "Hello everyone\n\n"
        "00:00:05.000 --> 00:00:08.000\n"
        "Welcome to my channel\n"
    )
    text = metadata_module._extract_transcript_text([str(vtt_file)])
    assert text == "Hello everyone Welcome to my channel"


def test_extract_transcript_text_strips_srt_formatting(tmp_path):
    srt_file = tmp_path / "test.en.srt"
    srt_file.write_text(
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Hello everyone\n\n"
        "2\n"
        "00:00:05,000 --> 00:00:08,000\n"
        "Welcome to my channel\n"
    )
    text = metadata_module._extract_transcript_text([str(srt_file)])
    assert text == "Hello everyone Welcome to my channel"


def test_extract_transcript_text_strips_vtt_tags(tmp_path):
    vtt_file = tmp_path / "test.en.vtt"
    vtt_file.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:04.000\n"
        "<c>Hello</c> <c>everyone</c>\n"
    )
    text = metadata_module._extract_transcript_text([str(vtt_file)])
    assert text == "Hello everyone"


def test_extract_transcript_text_combines_multiple_languages(tmp_path):
    en_file = tmp_path / "test.en.vtt"
    en_file.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n")
    hi_file = tmp_path / "test.hi.vtt"
    hi_file.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nनमस्ते\n"
    )
    text = metadata_module._extract_transcript_text([str(en_file), str(hi_file)])
    assert "Hello" in text
    assert "नमस्ते" in text


def test_extract_transcript_text_skips_unreadable_file(tmp_path, caplog):
    vtt_file = tmp_path / "test.en.vtt"
    vtt_file.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n")
    missing = tmp_path / "missing.vtt"
    text = metadata_module._extract_transcript_text([str(missing), str(vtt_file)])
    assert text == "Hello"


# ── Language detection ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("Hello everyone welcome to my channel", "English"),
        ("This is a test video about cooking", "English"),
        ("नमस्ते आपका स्वागत है", "Hindi"),
        ("यह एक हिंदी वीडियो है", "Hindi"),
        ("Hello दोस्तों आज का video बहुत खास है", "Hinglish"),
            ("Mumbai ki galiyon ka swaad - स्वाद", "Hinglish"),
    ],
)
def test_detect_language(text, expected):
    assert metadata_module._detect_language(text) == expected


# ── Transcript and duration in generation context ───────────────────────────────


def test_generation_context_includes_transcript_and_duration(monkeypatch, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: MockMetadataProvider())
    metadata_service.store_video_context(job.id, transcript="Hello everyone welcome", video_duration=120.5)
    try:
        context = metadata_service._build_generation_context(job.id, None)
        assert context.transcript == "Hello everyone welcome"
        assert context.video_duration == 120.5
        assert "Transcript: Hello everyone welcome" in context.final_prompt
        assert "Video duration: 120.5 seconds" in context.final_prompt
    finally:
        metadata_service.delete(job.id)


def test_generation_context_detects_language_from_transcript(monkeypatch, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: MockMetadataProvider())
    metadata_service.store_video_context(job.id, transcript="नमस्ते आपका स्वागत है")
    try:
        context = metadata_service._build_generation_context(job.id, None)
        assert context.detected_language == "Hindi"
        assert "Detected language: Hindi" in context.final_prompt
    finally:
        metadata_service.delete(job.id)


def test_generation_context_transcript_defaults_to_none(monkeypatch, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: MockMetadataProvider())
    context = metadata_service._build_generation_context(job.id, None)
    assert context.transcript is None
    assert context.video_duration is None
    assert context.detected_language is None


def test_generation_context_optional_values_omitted_when_none(monkeypatch, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: MockMetadataProvider())
    context = metadata_service._build_generation_context(job.id, None)
    assert "Transcript:" not in context.final_prompt
    assert "Video duration:" not in context.final_prompt
    assert "Detected language:" not in context.final_prompt


def test_store_video_context_does_not_leak_between_jobs():
    job_a = job_store.create("https://youtube.example/watch?v=a")
    job_b = job_store.create("https://youtube.example/watch?v=b")
    try:
        metadata_service.store_video_context(job_a.id, transcript="Hello", video_duration=30.0)
        metadata_service.store_video_context(job_b.id, transcript="World", video_duration=60.0)
        ctx_a = metadata_service._build_generation_context(job_a.id, None)
        ctx_b = metadata_service._build_generation_context(job_b.id, None)
        assert ctx_a.transcript == "Hello"
        assert ctx_a.video_duration == 30.0
        assert ctx_b.transcript == "World"
        assert ctx_b.video_duration == 60.0
    finally:
        metadata_service.delete(job_a.id)
        metadata_service.delete(job_b.id)
        job_store.delete(job_a.id)
        job_store.delete(job_b.id)


def test_store_video_context_accepts_partial_data(monkeypatch, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: MockMetadataProvider())
    metadata_service.store_video_context(job.id, transcript="Only transcript")
    try:
        context = metadata_service._build_generation_context(job.id, None)
        assert context.transcript == "Only transcript"
        assert context.video_duration is None
    finally:
        metadata_service.delete(job.id)


def test_store_video_context_partial_duration_only(monkeypatch):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: MockMetadataProvider())
    job = job_store.create("https://youtube.example/watch?v=dur-only")
    try:
        metadata_service.store_video_context(job.id, video_duration=90.0)
        context = metadata_service._build_generation_context(job.id, None)
        assert context.transcript is None
        assert context.video_duration == 90.0
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)


def test_store_video_context_ignores_empty_transcript(monkeypatch, job):
    monkeypatch.setattr(metadata_module, "get_metadata_provider", lambda: MockMetadataProvider())
    metadata_service.store_video_context(job.id, transcript="  ")
    try:
        context = metadata_service._build_generation_context(job.id, None)
        assert context.transcript is None
    finally:
        metadata_service.delete(job.id)


# ── Workflow integration: transcript/duration pipeline capture ──────────────────


def test_workflow_captures_transcript_and_duration_from_pipeline(monkeypatch):
    """Verify the workflow adapter stores transcript and duration on
    the metadata service when the pipeline context provides them."""
    from src.pipeline.context import PipelineContext
    from src.pipeline.models import StepRecord, PipelineResult

    captured_context = {}

    class RecordingProvider:
        name = "record"
        model = "record-v1"

        def generate(self, context):
            captured_context["context"] = context
            return {"title": "T", "description": "D", "tags": ["t"]}

    class FakeRunnerWithSubs:
        def __init__(self, settings, registry, downloader, progress):
            self.progress = progress
            self.downloader = downloader

        def run(self, workflow):
            step_record = StepRecord(
                name="download",
                type="step",
                status="completed",
                duration=1.0,
            )
            context = PipelineContext(
                workspace=Path("/tmp"),
                workflow_directory=Path("/tmp"),
            )
            context.metadata["download"] = {
                "success": True,
                "url": "https://youtube.com/watch?v=test",
                "title": "Test Video",
                "duration": 300.5,
                "subtitles": {},
                "file_path": "/tmp/test.mp4",
                "error": None,
            }
            self.progress("step_started", context, step_record)
            self.progress("step_completed", context, step_record)
            return SimpleNamespace(output_file=Path("/tmp/output.mp4"))

    monkeypatch.setattr(workflow_module, "PipelineRunner", FakeRunnerWithSubs)
    monkeypatch.setattr(workflow_module, "default_registry", lambda: object())
    monkeypatch.setattr(workflow_module, "HardenedDownloader", lambda settings: object())
    monkeypatch.setattr(metadata_module, "get_metadata_provider", RecordingProvider)
    monkeypatch.setattr(
        workflow_module.youtube_upload_service,
        "upload_job",
        _fake_successful_upload,
    )

    job = job_store.create("https://youtube.com/watch?v=pipeline-test")
    try:
        workflow_module._execute(job.id, object(), object())
        ctx = captured_context["context"]
        assert ctx.video_duration == 300.5
        assert ctx.transcript is None  # No subtitle files existed
        assert ctx.detected_language is None
        assert "Video duration: 300.5 seconds" in ctx.final_prompt
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)


def test_workflow_captures_transcript_from_subtitle_files(monkeypatch, tmp_path):
    from src.pipeline.context import PipelineContext
    from src.pipeline.models import StepRecord

    captured_context = {}

    class RecordingProvider:
        name = "record"
        model = "record-v1"

        def generate(self, context):
            captured_context["context"] = context
            return {"title": "T", "description": "D", "tags": ["t"]}

    sub_file = tmp_path / "test.en.vtt"
    sub_file.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:03.000\n"
        "This is a test transcript\n\n"
        "00:00:04.000 --> 00:00:06.000\n"
        "With multiple lines of content\n"
    )

    class FakeRunnerWithSubs:
        def __init__(self, settings, registry, downloader, progress):
            self.progress = progress
            self.downloader = downloader

        def run(self, workflow):
            step_record = StepRecord(
                name="download",
                type="step",
                status="completed",
                duration=1.0,
            )
            context = PipelineContext(
                workspace=Path("/tmp"),
                workflow_directory=Path("/tmp"),
            )
            context.metadata["download"] = {
                "success": True,
                "url": "https://youtube.com/watch?v=test",
                "title": "Test Video",
                "duration": 60.0,
                "subtitles": {"en": str(sub_file)},
                "file_path": str(tmp_path / "test.mp4"),
                "error": None,
            }
            self.progress("step_started", context, step_record)
            self.progress("step_completed", context, step_record)
            return SimpleNamespace(output_file=Path("/tmp/output.mp4"))

    monkeypatch.setattr(workflow_module, "PipelineRunner", FakeRunnerWithSubs)
    monkeypatch.setattr(workflow_module, "default_registry", lambda: object())
    monkeypatch.setattr(workflow_module, "HardenedDownloader", lambda settings: object())
    monkeypatch.setattr(metadata_module, "get_metadata_provider", RecordingProvider)
    monkeypatch.setattr(
        workflow_module.youtube_upload_service,
        "upload_job",
        _fake_successful_upload,
    )

    job = job_store.create("https://youtube.com/watch?v=sub-test")
    try:
        workflow_module._execute(job.id, object(), object())
        ctx = captured_context["context"]
        assert ctx.video_duration == 60.0
        assert ctx.transcript is not None
        assert "This is a test transcript" in ctx.transcript
        assert "With multiple lines of content" in ctx.transcript
        assert ctx.detected_language == "English"
        assert "Video duration: 60 seconds" in ctx.final_prompt
        assert "This is a test transcript" in ctx.final_prompt
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)
