"""Backend tests for the YouTube upload workflow stage."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app.models.metadata import VideoMetadata
from app.services import destinations as dest_service
from app.services import workflow as workflow_module
from app.services import youtube_upload as youtube_upload_module
from app.services.jobs import job_store
from app.services.metadata import metadata_service
from app.services.youtube_oauth import access_token_for_destination
from app.services.youtube_upload import (
    UploadMetadata,
    YouTubeUploadError,
    YouTubeUploadResult,
    YouTubeUploadService,
    YouTubeUploader,
)


def _create_test_destination() -> str:
    """Create a test YouTube destination in SQLite and return its id."""
    dest = dest_service.upsert_connected_channel(
        channel_title="Test Channel",
        channel_id="UC-test-channel-123",
        thumbnail="",
        description="Test destination for unit tests",
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        token_expires_at=None,
    )
    return dest.id


class CaptureUploader:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[Path, UploadMetadata]] = []

    def upload(self, *, video_path, metadata, progress):
        self.calls.append((video_path, metadata))
        progress(96, "Preparing YouTube upload...")
        if self.fail:
            raise YouTubeUploadError("quota exceeded")
        progress(99, "Finalizing YouTube upload...")
        return YouTubeUploadResult(
            video_id="yt-video-1",
            video_url="https://www.youtube.com/watch?v=yt-video-1",
            uploaded_at=datetime.now(timezone.utc),
            privacy_status="private",
        )


def test_upload_service_uses_generated_metadata_and_persists_result(tmp_path, monkeypatch):
    output = tmp_path / "processed.mp4"
    output.write_bytes(b"video")
    uploader = CaptureUploader()
    monkeypatch.setattr(
        "app.services.youtube_upload.access_token_for_destination",
        lambda destination_id: "test-access-token",
    )
    monkeypatch.setattr(
        youtube_upload_module, "YouTubeUploader", lambda access_token: uploader
    )
    service = YouTubeUploadService()
    destination_id = _create_test_destination()
    job = job_store.create("https://youtube.example/watch?v=upload")
    job_store.set_status(job.id, "running", output_file=str(output))
    metadata = VideoMetadata(
        job_id=job.id,
        title="Generated title",
        description="Generated description",
        tags=["cashcow", "upload"],
        generated_at=datetime.now(timezone.utc),
        provider="test",
        model="test",
        editable=True,
    )
    metadata_service._metadata[job.id] = metadata

    try:
        result = service.upload_job(job.id, destination_id, progress=lambda progress, message: None)

        latest = job_store.get(job.id)
        assert result.video_id == "yt-video-1"
        assert latest is not None
        assert latest.youtube_upload_status == "uploaded"
        assert latest.youtube_video_id == "yt-video-1"
        assert latest.youtube_video_url == "https://www.youtube.com/watch?v=yt-video-1"
        assert latest.youtube_uploaded_at is not None
        assert latest.upload_attempts == 1
        assert uploader.calls == [(output, UploadMetadata("Generated title", "Generated description", ["cashcow", "upload"]))]
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)


def test_upload_service_falls_back_to_title_seed_when_metadata_is_unavailable(tmp_path, monkeypatch):
    output = tmp_path / "processed.mp4"
    output.write_bytes(b"video")
    uploader = CaptureUploader()
    monkeypatch.setattr(
        "app.services.youtube_upload.access_token_for_destination",
        lambda destination_id: "test-access-token",
    )
    monkeypatch.setattr(
        youtube_upload_module, "YouTubeUploader", lambda access_token: uploader
    )
    service = YouTubeUploadService()
    destination_id = _create_test_destination()
    job = job_store.create(
        "https://youtube.example/watch?v=fallback",
        title_seed="Seed title",
    )
    job_store.set_status(job.id, "running", output_file=str(output))

    try:
        service.upload_job(job.id, destination_id, progress=lambda progress, message: None)

        assert uploader.calls[0][1] == UploadMetadata("Seed title", "", [])
    finally:
        job_store.delete(job.id)


def test_workflow_upload_failure_preserves_processed_job(monkeypatch):
    class FakeRunner:
        def __init__(self, settings, registry, downloader, progress):
            self.progress = progress

        def run(self, workflow):
            return SimpleNamespace(output_file=Path("/tmp/processed.mp4"))

    monkeypatch.setattr(workflow_module, "PipelineRunner", FakeRunner)
    monkeypatch.setattr(workflow_module, "default_registry", lambda: object())
    monkeypatch.setattr(workflow_module, "HardenedDownloader", lambda settings: object())
    monkeypatch.setattr(
        workflow_module.metadata_service,
        "generate",
        lambda job_id, log, fallback=True: job_store.set_metadata_status(job_id, "available"),
    )

    def fake_upload_job(job_id, destination_id, progress, log):
        raise YouTubeUploadError("network down")

    monkeypatch.setattr(
        workflow_module.youtube_upload_service,
        "upload_job",
        fake_upload_job,
    )

    destination_id = _create_test_destination()
    job = job_store.create(
        "https://youtube.example/watch?v=upload-fail",
        destination_ids=[destination_id],
    )
    try:
        workflow_module._execute(job.id, object(), object())

        latest = job_store.get(job.id)
        assert latest is not None
        assert latest.status == "upload_failed"
        assert latest.output_file == "/tmp/processed.mp4"
        assert latest.metadata_status == "available"
        assert latest.progress == 99
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)


def test_retry_youtube_upload_reuses_existing_output_and_metadata(monkeypatch, tmp_path):
    output = tmp_path / "processed.mp4"
    output.write_bytes(b"video")
    calls = []

    def fake_upload(job_id, destination_id, progress, log):
        calls.append(job_id)
        result = YouTubeUploadResult(
            video_id="retry-id",
            video_url="https://www.youtube.com/watch?v=retry-id",
            uploaded_at=datetime.now(timezone.utc),
            privacy_status="private",
        )
        progress(99, "Finalizing YouTube upload...")
        return result

    monkeypatch.setattr("app.api.jobs.youtube_upload_service.upload_job", fake_upload)
    monkeypatch.setattr(
        "app.api.jobs.youtube_upload_service.upload_job",
        fake_upload,
    )
    monkeypatch.setattr(
        "app.api.jobs.destinations.destination_exists",
        lambda destination_id: True,
    )
    destination_id = _create_test_destination()
    job = job_store.create(
        "https://youtube.example/watch?v=retry",
        destination_ids=[destination_id],
    )
    job_store.set_status(job.id, "upload_failed", output_file=str(output))
    job_store.set_destination_status(job.id, destination_id, "failed", error="previous failure")

    try:
        response = TestClient(app).post(f"/jobs/{job.id}/youtube/retry")

        assert response.status_code == 200
        payload = response.json()
        assert calls == [job.id]
        assert payload["status"] == "completed"
    finally:
        job_store.delete(job.id)


def test_youtube_uploader_authorizes_session_and_video_upload(monkeypatch, tmp_path):
    output = tmp_path / "processed.mp4"
    output.write_bytes(b"video")
    requests = []

    class HeaderResponse:
        headers = {"Location": "https://upload.example/session"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b""

    class JsonResponse:
        def __init__(self, payload):
            self._payload = payload

        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self._payload).encode("utf-8")

    def fake_urlopen(request, timeout):
        requests.append(request)
        if len(requests) == 1:
            return HeaderResponse()
        return JsonResponse({"id": "real-id"})

    monkeypatch.setattr(youtube_upload_module, "urlopen", fake_urlopen)

    result = YouTubeUploader(access_token="pre-authed-token").upload(
        video_path=output,
        metadata=UploadMetadata("Title", "Description", ["tag"]),
        progress=lambda progress, message: None,
    )

    assert result.video_id == "real-id"
    assert requests[0].headers["Authorization"] == "Bearer pre-authed-token"
    assert requests[1].headers["Authorization"] == "Bearer pre-authed-token"
