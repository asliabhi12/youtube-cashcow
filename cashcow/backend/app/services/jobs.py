"""In-memory store for jobs.

Holds jobs for the lifetime of the process only; there is no persistence
yet. A module-level singleton (`job_store`) is shared across requests.
"""

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.models.job import Job, JobStatus, MetadataStatus
from app.services.job_logs import job_log_hub

# Statuses at which a job has begun executing (left the queue) and reached a
# terminal state, used to stamp the started/finished timestamps exactly once.
_RUNNING_STATUSES = {"running"}
_TERMINAL_STATUSES = {"completed", "failed"}


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
        profile_id: str = "custom",
        export_quality: str = "balanced",
        title_seed: str | None = None,
    ) -> Job:
        """Create a pending job for the given URL and creative profile."""
        job = Job(
            id=str(uuid4()),
            url=url,
            status="pending",
            created_at=datetime.now(timezone.utc),
            profile_id=profile_id,
            export_quality=export_quality,
            title_seed=title_seed,
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

        The first transition into a running state stamps ``started_at`` (so the
        UI's elapsed timer excludes queue waiting time), and the first transition
        into a terminal state stamps ``finished_at`` and pins progress to 100 on
        success. On failure, progress is left frozen at whatever it last reached.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = status
            if status in _RUNNING_STATUSES and job.started_at is None:
                job.started_at = datetime.now(timezone.utc)
            if status in _TERMINAL_STATUSES and job.finished_at is None:
                job.finished_at = datetime.now(timezone.utc)
            if status == "completed":
                # Success always ends at exactly 100%.
                job.progress = 100
            if output_file is not None:
                job.output_file = output_file
            if error is not None:
                job.error = error

    def set_progress(
        self,
        job_id: str,
        progress: int,
        status_message: str,
    ) -> Job | None:
        """Update a job's progress percentage and status line, forward-only.

        Progress is the single source of truth for the overall bar. It is clamped
        to ``[0, 100]`` and can never move backwards: a lower value than the job
        already reached leaves the number untouched (only the status text
        updates). This is the one place the monotonic guarantee is enforced, so
        every caller — pipeline events, terminal transitions — is safe. Returns
        the updated job (for the caller to broadcast), or None if it is gone.
        """
        clamped = max(0, min(100, progress))
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if clamped > job.progress:
                job.progress = clamped
            job.status_message = status_message
            return job

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

    def set_has_metadata(self, job_id: str, has_metadata: bool) -> None:
        """Update a job's metadata availability flag. Missing jobs are ignored."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.has_metadata = has_metadata
            job.metadata_status = "available" if has_metadata else "unavailable"

    def set_metadata_status(self, job_id: str, status: MetadataStatus) -> None:
        """Update a job's metadata generation state. Missing jobs are ignored."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.metadata_status = status
            job.has_metadata = status == "available"


# Process-wide store shared by all requests.
job_store = JobStore()
