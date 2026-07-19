"""Job CRUD routes plus per-job log access.

Accepts a URL, creates an in-memory job, and starts its workflow. Also exposes
each job's high-level logs, both as a one-shot history and as a live Server-Sent
Events stream driven by the workflow adapter.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse

from app.models.job import Job, JobCreate, JobLogEntry, JobProgress
from app.services import app_settings, profiles
from app.services.job_logs import CLOSE, job_log_hub
from app.services.jobs import job_store
from app.services import job_progress
from app.services.presets import is_quality
from app.services.queue import job_queue
from app.services.youtube_upload import YouTubeUploadError, youtube_upload_service
from app.services.workflow import request_workflow_cancel

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _with_queue_position(job: Job) -> Job:
    """Return the job annotated with its live FIFO queue position.

    Position is meaningful only while the job is ``queued``; it is recomputed
    from the queue on every read (never stored), so it always reflects the
    current line even as jobs ahead finish or are removed.
    """
    if job.status == "queued":
        job.queue_position = job_queue.position(job.id)
    else:
        job.queue_position = None
    return job


def _sse(data: str, *, event: str | None = None) -> str:
    """Format one Server-Sent Event frame.

    ``data`` is expected to be a single JSON line (JSON escapes any newlines),
    so it maps to a single ``data:`` field. An optional ``event`` names the
    frame so the client can distinguish log entries from the terminal signal.
    """
    prefix = f"event: {event}\n" if event is not None else ""
    return f"{prefix}data: {data}\n\n"


@router.post("", response_model=Job, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate) -> Job:
    """Create a job and submit it to the FIFO queue.

    Validates the creative profile (profile id and export quality must be known),
    then returns immediately with the created job. The queue starts the job at
    once if no other job is running, otherwise it waits its turn; either way the
    job's status transitions asynchronously as it is queued, run, and finished.
    """
    profile_id = payload.effective_profile_id
    if not profiles.profile_exists(profile_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown profile: '{profile_id}'",
        )
    if not is_quality(payload.export_quality):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown export quality: '{payload.export_quality}'",
        )

    job = job_store.create(
        payload.url,
        profile_id=profile_id,
        export_quality=payload.export_quality,
        title_seed=payload.title_seed,
    )
    # Remember this as the last-used profile so the Home page can re-open it.
    # Best-effort: a settings write failure must never fail the job.
    try:
        app_settings.set_last_profile(profile_id)
    except Exception:  # noqa: BLE001 - persistence is non-critical here
        pass
    # Hand the job to the queue. It starts immediately when the single worker is
    # idle, or waits in line otherwise. The workflow adapter is never called
    # directly from here anymore, so multiple submits can never run concurrently.
    job_queue.submit(
        job.id,
        job.url,
        trim=payload.trim,
        profile_id=profile_id,
        export_quality=payload.export_quality,
    )
    # Re-read so the response reflects the status the queue just set (queued or
    # running) plus any position, rather than the transient "pending".
    return _with_queue_position(job_store.get(job.id) or job)


@router.get("", response_model=list[Job])
def list_jobs() -> list[Job]:
    """Return all jobs in creation order, each with its live queue position."""
    return [_with_queue_position(job) for job in job_store.list()]


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    """Return a single job (with its live queue position), or 404."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _with_queue_position(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str) -> None:
    """Delete a job (or remove it from the queue), with the running job protected.

    * A ``queued`` job is pulled out of the FIFO queue and its record removed.
    * A ``running`` job is refused with 409 — there is no safe mid-pipeline
      cancel, so the running job cannot be deleted.
    * A finished job (completed/failed) is simply removed from history.
    * An unknown id is 404.
    """
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status in {"running", "cancelling"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The running job can't be deleted; wait for it to finish.",
        )
    # Remove it from the waiting line first (no-op if it isn't queued), so the
    # worker never later tries to start a job whose record is gone.
    job_queue.remove(job_id)
    if not job_store.delete(job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


@router.post("/{job_id}/cancel", response_model=Job)
def cancel_job(job_id: str) -> Job:
    """Request cancellation for a queued or running workflow job."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status == "cancelled":
        return _with_queue_position(job)
    if job.status in {"completed", "failed", "upload_failed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Terminal jobs cannot be cancelled.",
        )

    original_status = job.status
    updated = job_store.request_cancel(job_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if original_status == "queued":
        job_queue.remove(job_id)
        job_store.set_status(job_id, "cancelled")
        _publish_progress(job_id, *job_progress.CANCELLED)
        job_log_hub.append(job_id, "WARNING", "Job cancelled")
        job_log_hub.close(job_id)
    else:
        _publish_progress(job_id, *job_progress.CANCELLING)
        job_log_hub.append(job_id, "WARNING", "Cancellation requested")
        request_workflow_cancel(job_id)

    latest = job_store.get(job_id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _with_queue_position(latest)


@router.post("/{job_id}/youtube/retry", response_model=Job)
def retry_youtube_upload(job_id: str) -> Job:
    """Retry only the final YouTube upload stage for a processed job."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.output_file is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job has no processed output to upload",
        )

    job_store.clear_cancel_request(job_id)
    job_store.set_status(job_id, "running")
    try:
        youtube_upload_service.upload_job(
            job_id,
            progress=lambda progress, message: _publish_progress(job_id, progress, message),
            log=lambda level, message: job_log_hub.append(job_id, level, message),
        )
    except YouTubeUploadError as exc:
        job_store.set_status(job_id, "upload_failed")
        _publish_progress(job_id, *job_progress.UPLOAD_FAILED)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    job_store.set_status(job_id, "completed")
    _publish_progress(job_id, *job_progress.UPLOAD_COMPLETE)
    latest = job_store.get(job_id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _with_queue_position(latest)


@router.get("/{job_id}/logs", response_model=list[JobLogEntry])
def get_job_logs(job_id: str) -> list[JobLogEntry]:
    """Return a job's log history, or 404 if the job does not exist."""
    if job_store.get(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_log_hub.history(job_id)


def _publish_progress(job_id: str, progress: int, status_message: str) -> None:
    job = job_store.set_progress(job_id, progress, status_message)
    if job is not None:
        job_log_hub.publish_progress(
            job_id, JobProgress(progress=job.progress, status=job.status_message)
        )


@router.get("/{job_id}/logs/events")
async def stream_job_logs(job_id: str) -> StreamingResponse:
    """Stream a job's logs as Server-Sent Events.

    Replays the log history collected so far, then emits each new entry as it is
    produced. When the job reaches a terminal state a final ``end`` event is
    sent so the client can close the connection; there is no polling. Returns
    404 if the job does not exist.
    """
    if job_store.get(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    loop = asyncio.get_running_loop()
    # Snapshot history plus the latest progress and subscribe atomically, so no
    # entry is missed between the two and none is delivered twice.
    snapshot, progress, queue = job_log_hub.subscribe(job_id, loop)

    async def event_stream() -> AsyncIterator[str]:
        try:
            for entry in snapshot:
                yield _sse(entry.model_dump_json())
            # Replay the current progress bar (if any) right after the backlog,
            # so a client joining mid-run renders the live percentage at once
            # rather than waiting for the next update.
            if progress is not None:
                yield _sse(progress.model_dump_json(), event="progress")
            while True:
                item = await queue.get()
                if item is CLOSE:
                    # Terminal signal: tell the client the stream is done so it
                    # stops reconnecting, then end the generator.
                    yield _sse(json.dumps({"job_id": job_id}), event="end")
                    return
                if isinstance(item, JobProgress):
                    # A named "progress" event so the client can tell overall
                    # progress apart from log lines on the one stream.
                    yield _sse(item.model_dump_json(), event="progress")
                else:
                    yield _sse(item.model_dump_json())
        finally:
            # Always drop the subscription, whether the job closed the stream or
            # the client disconnected mid-stream.
            job_log_hub.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable proxy buffering so entries flush to the client immediately.
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}/download")
def download_job_output(job_id: str) -> FileResponse:
    """Serve a completed job's output file as a download.

    The path comes from the job's own ``output_file`` (set by the engine, never
    by the client), so there is no user-controlled path to traverse. Returns 404
    if the job is missing or the file no longer exists, and 409 if the job has
    not produced an output yet.
    """
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "completed" or job.output_file is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job has no output to download yet",
        )

    path = Path(job.output_file)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file no longer exists",
        )

    # Serve under the title-derived name when known, else the on-disk name.
    filename = job.output_name or path.name
    return FileResponse(path, filename=filename, media_type="application/octet-stream")
