"""A minimal in-memory FIFO job queue that runs one job at a time.

This sits *above* the workflow adapter: it decides *when* a job's workflow is
handed to :func:`app.services.workflow.start_workflow`, never *how* it runs. The
engine under ``src/`` is untouched.

Rules, deliberately simple:

* One job runs at a time (no concurrency, no worker pool).
* Jobs start in submission order (FIFO); there are no priorities.
* When the running job reaches a terminal state, the next queued job starts
  automatically via a completion callback the adapter fires.
* Everything lives in memory for the process lifetime; nothing persists across a
  restart.

The queue owns only ordering and the single "busy" slot. Job records and their
status live in :data:`app.services.jobs.job_store` as before.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from threading import Lock

from app.models.job import TrimRange
from app.services.jobs import job_store
from app.services.workflow import start_workflow

logger = logging.getLogger(__name__)


@dataclass
class _QueuedJob:
    """A job waiting to run, with everything needed to start its workflow."""

    job_id: str
    url: str
    trim: TrimRange | None
    profile_id: str
    export_quality: str
    destination_ids: list[str]


class JobQueue:
    """A single-worker FIFO queue over the workflow adapter.

    A lock guards the waiting deque and the one running-job slot, since jobs are
    submitted from request threads while the completion callback fires from a
    workflow's background thread.
    """

    def __init__(self) -> None:
        self._waiting: deque[_QueuedJob] = deque()
        self._running_id: str | None = None
        self._lock = Lock()

    # --- Public API --------------------------------------------------------

    def submit(
        self,
        job_id: str,
        url: str,
        *,
        trim: TrimRange | None = None,
        profile_id: str = "custom",
        export_quality: str = "balanced",
        destination_ids: list[str] | None = None,
    ) -> None:
        """Enqueue a job and start it immediately if no job is running.

        The job is marked ``queued`` right away so the UI can show its place in
        line; it flips to ``running`` when the adapter actually starts it.
        """
        item = _QueuedJob(
            job_id=job_id,
            url=url,
            trim=trim,
            profile_id=profile_id,
            export_quality=export_quality,
            destination_ids=destination_ids or [],
        )
        with self._lock:
            self._waiting.append(item)
            job_store.set_status(job_id, "queued")
        self._start_next()

    def is_worker_busy(self) -> bool:
        """Whether a job is currently running."""
        with self._lock:
            return self._running_id is not None

    def queue_length(self) -> int:
        """How many jobs are waiting to run (excludes the running one)."""
        with self._lock:
            return len(self._waiting)

    def position(self, job_id: str) -> int | None:
        """1-based place of a job in the waiting line, or ``None`` if not queued."""
        with self._lock:
            for index, item in enumerate(self._waiting):
                if item.job_id == job_id:
                    return index + 1
            return None

    def remove(self, job_id: str) -> bool:
        """Drop a *waiting* job from the queue. Returns ``True`` if it was removed.

        The running job is never in the waiting line, so this can never cancel an
        in-flight workflow — callers must guard that separately.
        """
        with self._lock:
            for item in self._waiting:
                if item.job_id == job_id:
                    self._waiting.remove(item)
                    return True
            return False

    # --- Internals ---------------------------------------------------------

    def _start_next(self) -> None:
        """Start the next waiting job if the worker is idle.

        Claims the single slot under the lock (so two callers can't both start a
        job), then hands off outside the lock. If starting fails synchronously
        (e.g. an unresolved overlay asset while building the workflow), the job
        is failed and the next one is tried, so a bad job never wedges the queue.
        """
        with self._lock:
            if self._running_id is not None or not self._waiting:
                return
            item = self._waiting.popleft()
            self._running_id = item.job_id

        try:
            start_workflow(
                item.job_id,
                item.url,
                trim=item.trim,
                profile_id=item.profile_id,
                export_quality=item.export_quality,
                destination_ids=item.destination_ids,
                on_complete=self._on_complete,
            )
        except Exception as exc:  # noqa: BLE001 - keep the queue moving
            logger.exception("Failed to start job %s", item.job_id)
            job_store.set_status(item.job_id, "failed", error=str(exc))
            with self._lock:
                self._running_id = None
            # Try the next job; the failed one is out of the way.
            self._start_next()

    def _on_complete(self, job_id: str) -> None:
        """Free the worker slot and start the next job.

        Fired by the adapter from the finishing job's background thread once it
        reaches any terminal state (completed or failed). Guarded so a late
        callback for an already-cleared job can't start two jobs at once.
        """
        with self._lock:
            if self._running_id == job_id:
                self._running_id = None
        self._start_next()


# Process-wide queue shared by all requests.
job_queue = JobQueue()
