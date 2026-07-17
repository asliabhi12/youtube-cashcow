"""Compare real hardware and software encodes using the existing runner."""

from pathlib import Path
from tempfile import TemporaryDirectory
from .encoder import PerformanceEncoder
from .models import BenchmarkResult
from .profiler import EncodingProfiler


class Benchmark:
    """Produce comparable, typed reports for a local media input."""

    def __init__(self, encoder: PerformanceEncoder) -> None:
        self.encoder = encoder

    @classmethod
    def from_processor(cls, processor) -> "Benchmark":
        return cls(PerformanceEncoder.from_processor(processor))

    def compare(self, input_file: str | Path, *, software: bool = True, hardware: bool = True) -> list[BenchmarkResult]:
        source = Path(input_file)
        if not source.is_file():
            raise FileNotFoundError(f"Benchmark input does not exist: {source}")
        reports: list[BenchmarkResult] = []
        with TemporaryDirectory(prefix="cashcow_benchmark_") as directory:
            root = Path(directory)
            if hardware and self.encoder.capabilities.available:
                reports.append(self._run(source, root / "hardware.mp4", False))
            if software:
                reports.append(self._run(source, root / "software.mp4", True))
        return reports

    def _run(self, source: Path, output: Path, force_software: bool) -> BenchmarkResult:
        profiler = EncodingProfiler(); profiler.start()
        decision, stderr, elapsed = self.encoder.encode(source, output, force_software=force_software)
        metrics = profiler.finish(output, decision, stderr, elapsed)
        return BenchmarkResult(input_file=source, output_file=output, codec=decision.encoder, backend=decision.backend, metrics=metrics)
