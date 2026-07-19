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
    assert "Metadata validation failed" in caplog.text


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
    monkeypatch.setattr(workflow_module.metadata_service, "generate", lambda job_id: None)
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
        assert latest.has_metadata is False
        assert latest.metadata_status == "unavailable"
        assert metadata_service.get(job.id) is None
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
