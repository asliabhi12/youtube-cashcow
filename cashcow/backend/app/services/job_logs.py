"""Per-job log storage and live fan-out.

Each job keeps its own in-memory log history. New entries are produced by the
workflow adapter on a background thread, while readers (the SSE endpoint) live
in the async event loop. Because ``asyncio.Queue`` is not thread-safe, entries
are handed to subscribers via ``loop.call_soon_threadsafe``.

Connecting to a running job must neither miss nor duplicate entries: the
snapshot of existing history and the subscription for future entries are taken
atomically under a single lock, so any given entry is either already in the
snapshot or delivered through the queue — never both, never neither.
"""

import asyncio
import threading
from datetime import datetime, timezone

from app.models.job import JobLogEntry, JobLogLevel, JobProgress

# Sentinel pushed onto a subscriber's queue when its job reaches a terminal
# state, so the SSE generator can emit a final event and close cleanly rather
# than blocking on the queue forever.
CLOSE = object()

# A subscriber is the event loop that will drain the queue plus the queue
# itself; the loop is needed to schedule thread-safe puts from the worker.
_Subscriber = tuple[asyncio.AbstractEventLoop, "asyncio.Queue[object]"]


class JobLogHub:
    """Store per-job log history and stream new entries to live subscribers.

    A single lock guards history, the subscriber registry, and the set of
    closed jobs so that appends and subscriptions cannot interleave.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: dict[str, list[JobLogEntry]] = {}
        self._subscribers: dict[str, list[_Subscriber]] = {}
        self._closed: set[str] = set()
        # Latest progress per job. Only the newest value is kept (progress is a
        # single evolving bar, not a history), so a client subscribing mid-run
        # can render the current bar immediately from this snapshot.
        self._progress: dict[str, JobProgress] = {}

    def append(self, job_id: str, level: JobLogLevel, message: str) -> JobLogEntry:
        """Record a log entry for a job and push it to any live subscribers."""
        entry = JobLogEntry(
            timestamp=datetime.now(timezone.utc),
            level=level,
            message=message,
        )
        with self._lock:
            self._history.setdefault(job_id, []).append(entry)
            subscribers = list(self._subscribers.get(job_id, ()))
        # Deliver outside the lock; puts are scheduled on each subscriber's loop
        # because asyncio queues are not safe to touch from this worker thread.
        for loop, queue in subscribers:
            loop.call_soon_threadsafe(queue.put_nowait, entry)
        return entry

    def publish_progress(self, job_id: str, progress: JobProgress) -> None:
        """Record a job's latest progress and push it to live subscribers.

        Unlike log entries, only the newest progress is retained (it replaces
        any prior value), so a late subscriber snapshots the current bar rather
        than replaying every intermediate percentage.
        """
        with self._lock:
            self._progress[job_id] = progress
            subscribers = list(self._subscribers.get(job_id, ()))
        for loop, queue in subscribers:
            loop.call_soon_threadsafe(queue.put_nowait, progress)

    def close(self, job_id: str) -> None:
        """Mark a job's log stream finished and notify live subscribers.

        Idempotent. Any later subscriber to an already-closed job receives the
        close sentinel immediately after its history snapshot (see subscribe).
        """
        with self._lock:
            self._closed.add(job_id)
            subscribers = list(self._subscribers.get(job_id, ()))
        for loop, queue in subscribers:
            loop.call_soon_threadsafe(queue.put_nowait, CLOSE)

    def history(self, job_id: str) -> list[JobLogEntry]:
        """Return a copy of a job's log history (empty if it has none)."""
        with self._lock:
            return list(self._history.get(job_id, ()))

    def subscribe(
        self, job_id: str, loop: asyncio.AbstractEventLoop
    ) -> tuple[list[JobLogEntry], JobProgress | None, "asyncio.Queue[object]"]:
        """Atomically snapshot history and subscribe to future entries.

        Returns the log history at subscription time, the latest progress (or
        None if none has been reported yet), and a queue that will receive every
        entry and progress update appended afterwards, followed by the close
        sentinel when the job terminates. If the job has already closed, the
        sentinel is enqueued immediately so the caller stops once it has drained
        the snapshot.
        """
        queue: "asyncio.Queue[object]" = asyncio.Queue()
        with self._lock:
            snapshot = list(self._history.get(job_id, ()))
            progress = self._progress.get(job_id)
            self._subscribers.setdefault(job_id, []).append((loop, queue))
            already_closed = job_id in self._closed
        if already_closed:
            # Called from the loop thread, so a direct put is safe here.
            queue.put_nowait(CLOSE)
        return snapshot, progress, queue

    def unsubscribe(self, job_id: str, queue: "asyncio.Queue[object]") -> None:
        """Remove a subscriber's queue, e.g. after a client disconnects."""
        with self._lock:
            subscribers = self._subscribers.get(job_id)
            if subscribers is None:
                return
            remaining = [(loop, q) for loop, q in subscribers if q is not queue]
            if remaining:
                self._subscribers[job_id] = remaining
            else:
                self._subscribers.pop(job_id, None)

    def clear(self, job_id: str) -> None:
        """Drop all state for a job (history, subscribers, closed flag).

        Called when a job is deleted so its logs do not outlive it.
        """
        with self._lock:
            self._history.pop(job_id, None)
            self._subscribers.pop(job_id, None)
            self._closed.discard(job_id)
            self._progress.pop(job_id, None)


# Process-wide hub shared by the adapter (writer) and the API (readers).
job_log_hub = JobLogHub()
