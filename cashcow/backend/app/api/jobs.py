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

from app.models.job import Job, JobCreate, JobLogEntry
from app.services.job_logs import CLOSE, job_log_hub
from app.services.jobs import job_store
from app.services.presets import is_preset, is_quality
from app.services.workflow import start_workflow

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
    """Create a pending job and start its workflow in the background.

    Validates the creative profile (preset and export quality must be known
    slugs), then returns immediately with the created job; processing runs
    asynchronously and updates the job's status as the workflow progresses.
    """
    if not is_preset(payload.preset):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown preset: '{payload.preset}'",
        )
    if not is_quality(payload.export_quality):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown export quality: '{payload.export_quality}'",
        )

    job = job_store.create(
        payload.url,
        preset=payload.preset,
        export_quality=payload.export_quality,
    )
    start_workflow(
        job.id,
        job.url,
        trim=payload.trim,
        preset=payload.preset,
        export_quality=payload.export_quality,
    )
    return job


@router.get("", response_model=list[Job])
def list_jobs() -> list[Job]:
    """Return all jobs in creation order."""
    return job_store.list()


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    """Return a single job, or 404 if it does not exist."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str) -> None:
    """Delete a job, or 404 if it does not exist."""
    if not job_store.delete(job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


@router.get("/{job_id}/logs", response_model=list[JobLogEntry])
def get_job_logs(job_id: str) -> list[JobLogEntry]:
    """Return a job's log history, or 404 if the job does not exist."""
    if job_store.get(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_log_hub.history(job_id)


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
    # Snapshot history and subscribe atomically so no entry is missed between
    # the two, and none is delivered twice.
    snapshot, queue = job_log_hub.subscribe(job_id, loop)

    async def event_stream() -> AsyncIterator[str]:
        try:
            for entry in snapshot:
                yield _sse(entry.model_dump_json())
            while True:
                item = await queue.get()
                if item is CLOSE:
                    # Terminal signal: tell the client the stream is done so it
                    # stops reconnecting, then end the generator.
                    yield _sse(json.dumps({"job_id": job_id}), event="end")
                    return
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
