"""Tests for hardware-aware performance services without real GPU hardware."""

from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

from src.config import load_config
from src.performance import Benchmark, EncoderSelector, HardwareBackend, HardwareDetector, PerformanceEncoder, WorkerPool
from src.performance.metrics import MetricsCollector
from src.performance.models import EncoderDecision, HardwareCapabilities


def test_detector_prioritizes_apple_videotoolbox(monkeypatch):
    runner = MagicMock()
    runner.run.return_value = (" V..... h264_videotoolbox\n V..... h264_nvenc\n V..... libx264", "", 0.01)
    monkeypatch.setattr("src.performance.detector.platform.system", lambda: "Darwin")
    monkeypatch.setattr("src.performance.detector.platform.machine", lambda: "arm64")
    detected = HardwareDetector(runner).detect()
    assert detected.backend is HardwareBackend.VIDEOTOOLBOX
    assert detected.available and "h264_videotoolbox" in detected.encoders


def test_selector_uses_software_fallback():
    selected = EncoderSelector().choose(hardware=HardwareCapabilities(platform="Linux", machine="x86_64", encoders=["libx264"]))
    assert selected.encoder == "libx264" and not selected.hardware


def test_selector_prefers_nvenc_when_available():
    selected = EncoderSelector().choose(hardware=HardwareCapabilities(platform="Linux", machine="x86_64", backend=HardwareBackend.NVENC, encoders=["h264_nvenc", "libx264"], available=True))
    assert selected.encoder == "h264_nvenc" and selected.backend is HardwareBackend.NVENC


def test_metrics_parse_ffmpeg_output(tmp_path):
    output = tmp_path / "out.mp4"; output.write_bytes(b"video")
    collector = MetricsCollector(); start = collector.start()
    metric = collector.collect(output, EncoderDecision(encoder="libx264", backend=HardwareBackend.SOFTWARE, hardware=False), "frame=2 fps=185.0 speed=4.2x", .1, start)
    assert metric.average_fps == 185.0 and metric.encoding_speed == 4.2 and metric.output_size_bytes == 5


def test_worker_pool_reports_progress_and_shutdown():
    updates = []
    with WorkerPool(2) as pool:
        result = pool.map(lambda value: value * 2, [1, 2, 3], lambda done, total: updates.append((done, total)))
    assert sorted(result) == [2, 4, 6] and updates[-1] == (3, 3)


def test_benchmark_generates_software_report(tmp_path):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source")
    settings = load_config("settings.yaml")
    runner = MagicMock()
    def fake_run(args):
        if "-encoders" in args:
            return " V..... libx264", "", .01
        Path(args[-1]).write_bytes(b"encoded")
        return "", "fps=60.0 speed=2.0x", .02
    runner.run.side_effect = fake_run
    reports = Benchmark(PerformanceEncoder(runner, settings)).compare(source, hardware=False)
    assert len(reports) == 1 and reports[0].codec == "libx264" and reports[0].metrics.average_fps == 60.0
