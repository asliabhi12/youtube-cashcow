"""Tests for hardware-aware performance services without real GPU hardware."""

import json
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

from src.config import load_config
from src.performance import Benchmark, BenchmarkProfile, DecoderDetector, EncoderSelector, HardwareBackend, HardwareDetector, PerformanceEncoder, WorkerPool
from src.performance.benchmark import DEFAULT_CLIP_SECONDS
from src.performance.metrics import MetricsCollector
from src.performance.models import BenchmarkResult, DecoderInfo, EncoderDecision, HardwareCapabilities, PerformanceMetrics
from src.processor.models import VideoInfo


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


def _software_runner(captured: list | None = None):
    """Build a MagicMock runner that mimics a software-only FFmpeg install."""
    runner = MagicMock()

    def fake_run(args, **kwargs):
        if "-encoders" in args:
            return " V..... libx264", "", 0.01
        if "-decoders" in args:
            return " V..... libx264\n V..... libdav1d", "", 0.01
        if captured is not None:
            captured.append(list(args))
        Path(args[-1]).write_bytes(b"encoded")
        return "", "fps=48.0 speed=1.5x", 0.02

    runner.run.side_effect = fake_run
    return runner


def _probe_for(info: VideoInfo) -> MagicMock:
    probe = MagicMock()
    probe.inspect.return_value = info
    return probe


def test_decoder_detects_software_av1():
    runner = MagicMock()
    runner.run.return_value = (" V..... libdav1d\n V..... h264", "", 0.01)
    decoded = DecoderDetector(runner).detect("av1", None)
    assert decoded.decoder == "libdav1d" and not decoded.hardware
    assert decoded.label == "Software (libdav1d)"


def test_decoder_reports_hardware_when_hwaccel_set():
    runner = MagicMock()
    runner.run.return_value = ("", "", 0.01)
    decoded = DecoderDetector(runner).detect("h264", "videotoolbox")
    assert decoded.hardware and decoded.decoder == "videotoolbox"
    assert decoded.label == "Hardware (videotoolbox)"


def test_benchmark_encoder_profile_limits_duration(tmp_path):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source")
    settings = load_config("settings.yaml")
    captured: list = []
    runner = _software_runner(captured)
    info = VideoInfo(path=source, width=3840, height=2160, fps=25.0, duration=213.0, codec="av1")
    bench = Benchmark(PerformanceEncoder(runner, settings), probe=_probe_for(info), decoder_detector=DecoderDetector(runner))
    reports = bench.run(source, profile=BenchmarkProfile.ENCODER)
    assert len(reports) == 1  # software-only install -> single report
    encode_args = captured[0]
    assert "-t" in encode_args and encode_args[encode_args.index("-t") + 1] == str(DEFAULT_CLIP_SECONDS)
    report = reports[0]
    assert report.profile is BenchmarkProfile.ENCODER
    assert report.resolution == "3840x2160" and report.input_codec == "av1"
    assert report.decoder and report.decoder.decoder == "libdav1d"


def test_benchmark_transcode_profile_uses_full_file(tmp_path):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source")
    settings = load_config("settings.yaml")
    captured: list = []
    runner = _software_runner(captured)
    info = VideoInfo(path=source, width=1920, height=1080, fps=30.0, duration=12.0, codec="h264")
    bench = Benchmark(PerformanceEncoder(runner, settings), probe=_probe_for(info), decoder_detector=DecoderDetector(runner))
    reports = bench.run(source, profile=BenchmarkProfile.TRANSCODE)
    assert "-t" not in captured[0]  # full file, no duration limit
    assert reports[0].profile is BenchmarkProfile.TRANSCODE


def test_benchmark_duration_override_caps_at_source_length(tmp_path):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source")
    settings = load_config("settings.yaml")
    captured: list = []
    runner = _software_runner(captured)
    info = VideoInfo(path=source, width=1280, height=720, fps=30.0, duration=5.0, codec="h264")
    bench = Benchmark(PerformanceEncoder(runner, settings), probe=_probe_for(info), decoder_detector=DecoderDetector(runner))
    bench.run(source, profile=BenchmarkProfile.ENCODER, duration=60.0)
    # Requested 60s but source is only 5s -> clip clamps to the source length.
    encode_args = captured[0]
    assert encode_args[encode_args.index("-t") + 1] == "5.0"


def test_benchmark_quality_profile_runs_multiple_presets(tmp_path):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source")
    settings = load_config("settings.yaml")
    runner = _software_runner()
    info = VideoInfo(path=source, width=1920, height=1080, fps=30.0, duration=120.0, codec="h264")
    bench = Benchmark(PerformanceEncoder(runner, settings), probe=_probe_for(info), decoder_detector=DecoderDetector(runner))
    reports = bench.run(source, profile=BenchmarkProfile.QUALITY)
    assert len(reports) == 3
    assert {r.preset for r in reports} == {"youtube_1080", "youtube_4k", "archive"}


def test_benchmark_result_json_export_round_trips(tmp_path):
    result = BenchmarkResult(
        input_file=tmp_path / "in.mp4", output_file=tmp_path / "out.mp4",
        codec="libx264", backend=HardwareBackend.SOFTWARE,
        metrics=PerformanceMetrics(duration_seconds=1.5, output_size_bytes=1000, average_fps=48.0, encoding_speed=1.5, encoder="libx264", hardware_used=False),
        profile=BenchmarkProfile.ENCODER, decoder=DecoderInfo(codec="av1", decoder="libdav1d", hardware=False),
        resolution="1920x1080", input_codec="av1", input_duration=120.0,
    )
    payload = json.loads(json.dumps(result.model_dump(mode="json")))
    assert payload["decoder"]["decoder"] == "libdav1d"
    assert payload["resolution"] == "1920x1080" and payload["profile"] == "encoder"
    assert payload["metrics"]["encoding_speed"] == 1.5


def test_metrics_speed_fallback_when_ffmpeg_silent(tmp_path):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source")
    settings = load_config("settings.yaml")
    runner = MagicMock()

    def fake_run(args, **kwargs):
        if "-encoders" in args:
            return " V..... libx264", "", 0.01
        if "-decoders" in args:
            return " V..... libx264", "", 0.01
        Path(args[-1]).write_bytes(b"encoded")
        return "", "frame=100", 2.0  # no speed= reported

    runner.run.side_effect = fake_run
    info = VideoInfo(path=source, width=1920, height=1080, fps=30.0, duration=10.0, codec="h264")
    bench = Benchmark(PerformanceEncoder(runner, settings), probe=_probe_for(info), decoder_detector=DecoderDetector(runner))
    report = bench.run(source, profile=BenchmarkProfile.ENCODER, duration=4.0)[0]
    # 4s clip encoded in 2.0s -> 2.0x realtime derived fallback.
    assert report.metrics.encoding_speed == 2.0
