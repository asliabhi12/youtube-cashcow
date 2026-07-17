"""Build typed metrics from FFmpeg output and resource samples."""

import re
from pathlib import Path
from .models import EncoderDecision, PerformanceMetrics
from .resources import ResourceMonitor, ResourceSnapshot


class MetricsCollector:
    def __init__(self, monitor: ResourceMonitor | None = None) -> None:
        self.monitor = monitor or ResourceMonitor()

    def start(self) -> ResourceSnapshot:
        return self.monitor.snapshot()

    def collect(self, output_file: str | Path, decision: EncoderDecision, stderr: str, duration: float, start: ResourceSnapshot) -> PerformanceMetrics:
        text = stderr.replace("\r", " ")
        fps = _last_number(r"fps=\s*([0-9.]+)", text)
        speed = _last_number(r"speed=\s*([0-9.]+)x", text)
        end = self.monitor.snapshot()
        output = Path(output_file)
        return PerformanceMetrics(
            duration_seconds=duration, output_size_bytes=output.stat().st_size,
            average_fps=fps, encoding_speed=speed,
            cpu_percent=self.monitor.cpu_percent(start, end), memory_bytes=end.memory_bytes,
            encoder=decision.encoder, hardware_used=decision.hardware,
        )


def _last_number(pattern: str, value: str) -> float | None:
    matches = re.findall(pattern, value)
    return float(matches[-1]) if matches else None
