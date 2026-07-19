"""Source-level checks for the completed-job metadata UI."""

from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "frontend"


def _read(relative: str) -> str:
    return (FRONTEND_ROOT / relative).read_text(encoding="utf-8")


def test_completed_job_metadata_ui_has_loading_and_unavailable_states():
    source = _read("app/jobs/page.tsx")

    assert 'initialJob.metadata_status === "generating"' in source
    assert 'initialJob.metadata_status === "unavailable"' in source
    assert "Generating AI metadata..." in source
    assert "AI metadata unavailable." in source


def test_completed_job_metadata_ui_has_field_copy_controls():
    source = _read("app/jobs/page.tsx")

    assert "metadataCopyText" in source
    assert "navigator.clipboard.writeText" in source
    assert 'field === "tags"' in source
    assert "Copied!" in source
    assert 'label="Title"' in source
    assert 'label="Description"' in source
    assert 'label="Tags"' in source


def test_job_api_exposes_metadata_status_type():
    source = _read("lib/api.ts")

    assert 'export type MetadataStatus = "idle" | "generating" | "available" | "unavailable";' in source
    assert "metadata_status: MetadataStatus;" in source
    assert '"cancelling"' in source
    assert '"cancelled"' in source


def test_job_api_exposes_youtube_upload_status_type():
    source = _read("lib/api.ts")

    assert 'export type YouTubeUploadStatus = "idle" | "uploading" | "uploaded" | "failed";' in source
    assert "youtube_upload_status: YouTubeUploadStatus;" in source
    assert "youtube_video_url: string | null;" in source


def test_jobs_ui_has_cancel_and_upload_retry_actions():
    api = _read("lib/api.ts")
    page = _read("app/jobs/page.tsx")

    assert "cancelJob" in api
    assert "retryYouTubeUpload" in api
    assert "/cancel" in api
    assert "/youtube/retry" in api
    assert "Stop" in page
    assert "Retry Upload" in page
    assert 'initialJob.status !== "upload_failed"' in page
