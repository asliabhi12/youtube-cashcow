"""In-memory store for jobs.

Holds jobs for the lifetime of the process only; there is no persistence
yet. A module-level singleton (`job_store`) is shared across requests.
"""

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.models.job import Job, JobStatus
from app.services.job_logs import job_log_hub


class JobStore:
    """Create, read, and delete jobs kept in memory.

    A lock guards every access because the workflow engine updates job status
    from a background thread while request handlers read and write concurrently.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def create(
        self,
        url: str,
        *,
        preset: str = "custom",
        export_quality: str = "balanced",
    ) -> Job:
        """Create a pending job for the given URL and creative profile."""
        job = Job(
            id=str(uuid4()),
            url=url,
            status="pending",
            created_at=datetime.now(timezone.utc),
            preset=preset,
            export_quality=export_quality,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def list(self) -> list[Job]:
        """Return all jobs in creation order."""
        with self._lock:
            return list(self._jobs.values())

    def get(self, job_id: str) -> Job | None:
        """Return the job with the given id, or None if it does not exist."""
        with self._lock:
            return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        """Remove a job and its logs. Return True if it existed, False otherwise."""
        with self._lock:
            existed = self._jobs.pop(job_id, None) is not None
        if existed:
            # Drop the job's log history and drop any live subscribers so the
            # logs do not outlive the job they describe.
            job_log_hub.clear(job_id)
        return existed

    def set_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        output_file: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update a job's status and optional result fields.

        Called as the workflow progresses. Missing jobs (e.g. deleted mid-run)
        are ignored so a late engine callback cannot resurrect them.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = status
            if output_file is not None:
                job.output_file = output_file
            if error is not None:
                job.error = error

    def set_output_name(self, job_id: str, output_name: str) -> None:
        """Set a job's title-derived download filename.

        Called mid-run once the video title is known (after download), not tied
        to a status transition. Missing jobs are ignored.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.output_name = output_name


# Process-wide store shared by all requests.
job_store = JobStore()
