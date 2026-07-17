"""Cancellation-aware, CPU-conscious thread worker pool for independent work."""

import os
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from threading import Event, Lock
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


class WorkerPool:
    """A small wrapper with explicit cancellation and graceful shutdown."""

    def __init__(self, workers: int | str = "auto") -> None:
        count = max(1, (os.cpu_count() or 1) - 1) if workers == "auto" else max(1, int(workers))
        self.workers = count
        self.cancel_event = Event()
        self._executor = ThreadPoolExecutor(max_workers=count, thread_name_prefix="cashcow-worker")
        self._closed = False

    def submit(self, operation: Callable[..., T], *args, **kwargs) -> Future[T]:
        if self._closed:
            raise RuntimeError("WorkerPool has been shut down")
        return self._executor.submit(self._run, operation, args, kwargs)

    def map(self, operation: Callable[[T], T], values: Iterable[T], progress: Callable[[int, int], None] | None = None) -> list[T]:
        futures = [self.submit(operation, value) for value in values]
        results: list[T] = []
        lock = Lock()
        for completed, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if progress:
                with lock:
                    progress(completed, len(futures))
        return results

    def cancel(self) -> None:
        self.cancel_event.set()
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._closed = True

    def shutdown(self, wait: bool = True) -> None:
        if not self._closed:
            self._executor.shutdown(wait=wait, cancel_futures=self.cancel_event.is_set())
            self._closed = True

    def _run(self, operation: Callable[..., T], args: tuple, kwargs: dict) -> T:
        if self.cancel_event.is_set():
            raise RuntimeError("WorkerPool work was cancelled")
        return operation(*args, **kwargs)

    def __enter__(self) -> "WorkerPool":
        return self

    def __exit__(self, *_exc) -> None:
        self.shutdown()
