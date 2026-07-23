"""YouTube upload service for the final workflow stage.

Each upload uses per-destination OAuth credentials so that multiple connected
YouTube channels can be published to independently.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import youtube_upload_config
from app.models.destination import JobDestinationStatus, UploadSettings
from app.models.job import JobLogLevel
from app.models.metadata import VideoMetadata
from app.services import destinations
from app.services.jobs import job_store
from app.services.metadata import metadata_service
from app.services.youtube_oauth import access_token_for_destination

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 60
VIDEO_URL_TEMPLATE = "https://www.youtube.com/watch?v={video_id}"


class YouTubeUploadError(RuntimeError):
    """Raised when the final YouTube upload stage cannot complete."""


@dataclass(frozen=True)
class UploadMetadata:
    title: str
    description: str
    tags: list[str]


@dataclass(frozen=True)
class YouTubeUploadResult:
    video_id: str
    video_url: str
    uploaded_at: datetime
    privacy_status: str


class YouTubeUploader:
    """OAuth-backed YouTube uploader using the resumable upload endpoint."""

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    def upload(
        self,
        *,
        video_path: Path,
        metadata: UploadMetadata,
        progress: Callable[[int, str], None],
    ) -> YouTubeUploadResult:
        if not video_path.is_file():
            raise YouTubeUploadError(f"Processed video not found: {video_path}")

        size = video_path.stat().st_size
        logger.info("YouTube upload starting: path=%s size=%s", video_path, size)
        progress(96, "Preparing YouTube upload...")
        session_url = self._start_resumable_session(metadata, size)
        progress(98, "Uploading video to YouTube...")
        response = self._upload_file(session_url, video_path)
        video_id = str(response.get("id") or "").strip()
        if not video_id:
            raise YouTubeUploadError("YouTube response did not include a video id")
        logger.info("YouTube upload completed: video_id=%s response=%s", video_id, response)
        progress(99, "Finalizing YouTube upload...")
        return YouTubeUploadResult(
            video_id=video_id,
            video_url=VIDEO_URL_TEMPLATE.format(video_id=video_id),
            uploaded_at=datetime.now(timezone.utc),
            privacy_status=youtube_upload_config.PRIVACY_STATUS,
        )

    def _start_resumable_session(
        self,
        metadata: UploadMetadata,
        size: int,
    ) -> str:
        body = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": youtube_upload_config.CATEGORY_ID,
            },
            "status": {
                "privacyStatus": youtube_upload_config.PRIVACY_STATUS,
                "selfDeclaredMadeForKids": youtube_upload_config.MADE_FOR_KIDS,
            },
        }
        request = Request(
            youtube_upload_config.RESUMABLE_UPLOAD_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(size),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                location = response.headers.get("Location")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise YouTubeUploadError(f"Could not start YouTube upload: {_error_detail(exc)}") from exc
        if not location:
            raise YouTubeUploadError("YouTube did not return a resumable upload URL")
        return location

    def _upload_file(self, session_url: str, video_path: Path) -> dict:
        data = video_path.read_bytes()
        request = Request(
            session_url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Length": str(len(data)),
                "Content-Type": "video/mp4",
            },
            method="PUT",
        )
        return _json_request(request)


class YouTubeUploadService:
    def __init__(self) -> None:
        pass

    def upload_job(
        self,
        job_id: str,
        destination_id: str,
        *,
        progress: Callable[[int, str], None],
        log: Callable[[JobLogLevel, str], None] | None = None,
    ) -> YouTubeUploadResult:
        job = job_store.get(job_id)
        if job is None:
            raise YouTubeUploadError("Job not found")
        if not job.output_file:
            raise YouTubeUploadError("Job has no processed output to upload")

        video_path = Path(job.output_file)
        upload_metadata = _metadata_for_job(job_id)
        _log(log, "INFO", f"YouTube upload started for destination {destination_id}.")
        _log(log, "INFO", f"Uploading processed video: {video_path} ({_file_size(video_path)} bytes)")

        access_token = access_token_for_destination(destination_id)
        uploader = YouTubeUploader(access_token)
        job_store.set_upload_started(job_id)

        try:
            result = uploader.upload(
                video_path=video_path,
                metadata=upload_metadata,
                progress=progress,
            )
        except Exception as exc:
            message = str(exc)
            logger.warning("YouTube upload failed for job %s destination %s: %s", job_id, destination_id, message)
            job_store.set_destination_status(
                job_id, destination_id, "failed", error=message,
            )
            job_store.set_upload_result(job_id, "failed", error=message)
            destinations.record_upload(
                job_id=job_id,
                destination_id=destination_id,
                status="failed",
                progress=0,
                upload_settings=UploadSettings(),
                error=message,
            )
            _log(log, "ERROR", f"YouTube upload failed for {destination_id}: {message}")
            raise YouTubeUploadError(message) from exc

        job_store.set_destination_status(
            job_id,
            destination_id,
            "success",
            video_id=result.video_id,
            video_url=result.video_url,
        )
        job_store.set_upload_result(
            job_id,
            "uploaded",
            video_id=result.video_id,
            video_url=result.video_url,
            uploaded_at=result.uploaded_at,
        )
        destinations.record_upload(
            job_id=job_id,
            destination_id=destination_id,
            status="success",
            progress=100,
            upload_settings=UploadSettings(),
            video_id=result.video_id,
            video_url=result.video_url,
        )
        _log(log, "INFO", f"YouTube upload complete for {destination_id}: {result.video_id}")
        return result


def _metadata_for_job(job_id: str) -> UploadMetadata:
    job = job_store.get(job_id)
    if job is None:
        raise YouTubeUploadError("Job not found")
    generated = metadata_service.get(job_id)
    if generated is not None:
        return _from_generated_metadata(generated)
    fallback_title = job.title_seed or _title_from_output_name(job.output_name) or "CashCow video"
    return UploadMetadata(title=fallback_title, description="", tags=[])


def _from_generated_metadata(metadata: VideoMetadata) -> UploadMetadata:
    return UploadMetadata(
        title=metadata.title,
        description=metadata.description,
        tags=metadata.tags,
    )


def _title_from_output_name(output_name: str | None) -> str | None:
    if output_name is None:
        return None
    return Path(output_name).stem.replace("_", " ").replace("-", " ").strip() or None


def _json_request(request: Request) -> dict:
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise YouTubeUploadError(_error_detail(exc)) from exc
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise YouTubeUploadError("YouTube returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise YouTubeUploadError("YouTube returned an unexpected response")
    return value


def _error_detail(exc: BaseException) -> str:
    if isinstance(exc, HTTPError):
        body = exc.read().decode("utf-8", errors="replace")
        return f"HTTP {exc.code}: {body or exc.reason}"
    return str(exc)


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _log(
    callback: Callable[[JobLogLevel, str], None] | None,
    level: JobLogLevel,
    message: str,
) -> None:
    if callback is not None:
        callback(level, message)


youtube_upload_service = YouTubeUploadService()
