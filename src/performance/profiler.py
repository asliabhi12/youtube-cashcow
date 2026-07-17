"""Small profiling façade used by benchmarks and application integrations."""

from pathlib import Path
from .metrics import MetricsCollector
from .models import EncoderDecision, PerformanceMetrics
from .resources import ResourceSnapshot


class EncodingProfiler:
    def __init__(self, collector: MetricsCollector | None = None) -> None:
        self.collector = collector or MetricsCollector()
        self._start: ResourceSnapshot | None = None

    def start(self) -> None:
        self._start = self.collector.start()

    def finish(self, output_file: str | Path, decision: EncoderDecision, stderr: str, duration: float) -> PerformanceMetrics:
        if self._start is None:
            raise RuntimeError("Profiler must be started before it is finished")
        return self.collector.collect(output_file, decision, stderr, duration, self._start)
