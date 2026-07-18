"""In-memory store for jobs.

Holds jobs for the lifetime of the process only; there is no persistence
yet. A module-level singleton (`job_store`) is shared across requests.
"""

from datetime import datetime, timezone
from uuid import uuid4

from app.models.job import Job


class JobStore:
    """Create, read, and delete jobs kept in memory."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, url: str) -> Job:
        """Create a pending job for the given URL and store it."""
        job = Job(
            id=str(uuid4()),
            url=url,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        self._jobs[job.id] = job
        return job

    def list(self) -> list[Job]:
        """Return all jobs in creation order."""
        return list(self._jobs.values())

    def get(self, job_id: str) -> Job | None:
        """Return the job with the given id, or None if it does not exist."""
        return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        """Remove a job. Return True if it existed, False otherwise."""
        return self._jobs.pop(job_id, None) is not None


# Process-wide store shared by all requests.
job_store = JobStore()
