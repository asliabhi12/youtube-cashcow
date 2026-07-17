"""Portable process resource snapshots without an optional psutil dependency."""

import os
import resource
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceSnapshot:
    wall_time: float
    cpu_time: float
    memory_bytes: int


class ResourceMonitor:
    def snapshot(self) -> ResourceSnapshot:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        memory = int(usage.ru_maxrss)
        # macOS reports bytes; Linux reports KiB.
        if os.name != "posix" or __import__("platform").system() != "Darwin":
            memory *= 1024
        return ResourceSnapshot(time.monotonic(), time.process_time(), memory)

    @staticmethod
    def cpu_percent(start: ResourceSnapshot, end: ResourceSnapshot) -> float:
        elapsed = max(end.wall_time - start.wall_time, 0.001)
        return round((end.cpu_time - start.cpu_time) / elapsed / max(os.cpu_count() or 1, 1) * 100, 2)
