"""Tests for workflow cancellation and upload-only retry behavior."""

import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app.models.job import JobProgress
from app.services import workflow as workflow_module
from app.services.jobs import job_store
from app.services.metadata import metadata_service
from app.services.youtube_upload import YouTubeUploadResult


def _record(name: str):
    return SimpleNamespace(name=name, detail=None)


def _patch_runner(monkeypatch, run):
    class FakeRunner:
        def __init__(self, settings, registry, downloader, progress):
            self.progress = progress

        def run(self, workflow):
            return run(self)

    monkeypatch.setattr(workflow_module, "PipelineRunner", FakeRunner)
    monkeypatch.setattr(workflow_module, "default_registry", lambda: object())


def test_cancel_during_download_marks_job_cancelled(monkeypatch):
    def run(runner):
        runner.progress("pipeline_started", object(), None)
        runner.progress("step_started", object(), _record("download"))
        job_store.request_cancel(job.id)
        runner.progress("step_completed", SimpleNamespace(metadata={}), _record("download"))

    job = job_store.create("https://youtube.example/watch?v=cancel-download")
    _patch_runner(monkeypatch, run)
    try:
        workflow_module._execute(job.id, object(), object())
        assert job_store.get(job.id).status == "cancelled"
    finally:
        job_store.delete(job.id)


def test_cancel_during_processing_marks_job_cancelled(monkeypatch):
    def run(runner):
        runner.progress("pipeline_started", object(), None)
        runner.progress("step_started", object(), _record("encode"))
        job_store.request_cancel(job.id)
        runner.progress("step_completed", SimpleNamespace(metadata={}), _record("encode"))

    job = job_store.create("https://youtube.example/watch?v=cancel-processing")
    _patch_runner(monkeypatch, run)
    try:
        workflow_module._execute(job.id, object(), object())
        assert job_store.get(job.id).status == "cancelled"
    finally:
        job_store.delete(job.id)


def test_cancel_during_metadata_marks_job_cancelled(monkeypatch):
    def run(runner):
        return SimpleNamespace(output_file=Path("/tmp/processed.mp4"))

    def generate(job_id, log):
        job_store.request_cancel(job_id)
        job_store.set_metadata_status(job_id, "available")

    job = job_store.create("https://youtube.example/watch?v=cancel-metadata")
    _patch_runner(monkeypatch, run)
    monkeypatch.setattr(workflow_module.metadata_service, "generate", generate)
    try:
        workflow_module._execute(job.id, object(), object())
        latest = job_store.get(job.id)
        assert latest.status == "cancelled"
        assert latest.output_file == "/tmp/processed.mp4"
        assert latest.metadata_status == "available"
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)


def test_cancel_during_upload_marks_job_cancelled(monkeypatch):
    def run(runner):
        return SimpleNamespace(output_file=Path("/tmp/processed.mp4"))

    def upload(job_id, progress, log):
        job_store.request_cancel(job_id)
        progress(98, "Uploading video to YouTube...")

    job = job_store.create("https://youtube.example/watch?v=cancel-upload")
    _patch_runner(monkeypatch, run)
    monkeypatch.setattr(workflow_module.metadata_service, "generate", lambda job_id, log: None)
    monkeypatch.setattr(workflow_module.youtube_upload_service, "upload_job", upload)
    try:
        workflow_module._execute(job.id, object(), object())
        latest = job_store.get(job.id)
        assert latest.status == "cancelled"
        assert latest.output_file == "/tmp/processed.mp4"
    finally:
        metadata_service.delete(job.id)
        job_store.delete(job.id)


def test_cancel_completed_job_is_rejected():
    job = job_store.create("https://youtube.example/watch?v=done")
    job_store.set_status(job.id, "completed")
    try:
        response = TestClient(app).post(f"/jobs/{job.id}/cancel")
        assert response.status_code == 409
    finally:
        job_store.delete(job.id)


def test_cancel_already_cancelled_job_is_idempotent():
    job = job_store.create("https://youtube.example/watch?v=cancelled")
    job_store.set_status(job.id, "cancelled")
    try:
        response = TestClient(app).post(f"/jobs/{job.id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
    finally:
        job_store.delete(job.id)


def test_upload_retry_does_not_restart_workflow(monkeypatch, tmp_path):
    output = tmp_path / "processed.mp4"
    output.write_bytes(b"video")
    calls = []

    def fake_upload(job_id, progress, log):
        calls.append(job_id)
        job_store.set_upload_started(job_id)
        job_store.set_upload_result(
            job_id,
            "uploaded",
            video_id="retry-only",
            video_url="https://www.youtube.com/watch?v=retry-only",
        )
        return YouTubeUploadResult(
            video_id="retry-only",
            video_url="https://www.youtube.com/watch?v=retry-only",
            uploaded_at=job_store.get(job_id).created_at,
            privacy_status="private",
        )

    def fail_submit(*args, **kwargs):
        raise AssertionError("upload retry must not submit a new workflow")

    monkeypatch.setattr("app.api.jobs.job_queue.submit", fail_submit)
    monkeypatch.setattr("app.api.jobs.youtube_upload_service.upload_job", fake_upload)
    job = job_store.create("https://youtube.example/watch?v=retry-only")
    job_store.set_status(job.id, "upload_failed", output_file=str(output))
    try:
        response = TestClient(app).post(f"/jobs/{job.id}/youtube/retry")
        assert response.status_code == 200
        assert calls == [job.id]
        assert response.json()["status"] == "completed"
        assert response.json()["youtube_video_id"] == "retry-only"
    finally:
        job_store.delete(job.id)
