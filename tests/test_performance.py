"""Tests for hardware-aware performance services without real GPU hardware."""

import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.config import load_config
from src.performance import Benchmark, BenchmarkProfile, DecoderDetector, EncoderSelector, HardwareBackend, HardwareDetector, PerformanceEncoder, PipelineBenchmark, PipelineTimeline, WorkerPool
from src.performance.benchmark import DEFAULT_CLIP_SECONDS
from src.performance.metrics import MetricsCollector
from src.performance.models import BenchmarkResult, DecoderInfo, EncoderDecision, HardwareCapabilities, PerformanceMetrics, StepTiming
from src.pipeline import PipelineStepError
from src.pipeline.models import StepRecord
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


def test_args_for_software_uses_crf_when_no_video_bitrate():
    decision = EncoderDecision(encoder="libx264", backend=HardwareBackend.SOFTWARE, hardware=False, crf=23, preset="medium")
    args = PerformanceEncoder.args_for(decision, audio_bitrate="192k")
    assert "-crf" in args and args[args.index("-crf") + 1] == "23"
    assert "-b:v" not in args
    assert args[args.index("-b:a") + 1] == "192k"


def test_args_for_video_bitrate_replaces_crf_on_software():
    decision = EncoderDecision(encoder="libx264", backend=HardwareBackend.SOFTWARE, hardware=False, crf=23, preset="medium")
    args = PerformanceEncoder.args_for(decision, audio_bitrate="192k", video_bitrate="8M")
    assert args[args.index("-b:v") + 1] == "8M"
    assert "-crf" not in args  # bitrate and CRF are mutually exclusive


def test_args_for_video_bitrate_overrides_hardware_defaults():
    decision = EncoderDecision(encoder="h264_videotoolbox", backend=HardwareBackend.VIDEOTOOLBOX, hardware=True, bitrate="8M")
    args = PerformanceEncoder.args_for(decision, audio_bitrate="192k", video_bitrate="12M")
    assert args[args.index("-b:v") + 1] == "12M"  # explicit setting wins over the decision default
    assert "-crf" not in args


def test_default_args_threads_video_bitrate_from_settings(tmp_path):
    settings = load_config("settings.yaml")
    settings.ffmpeg.video_bitrate = "5M"
    settings.ffmpeg.audio_bitrate = "256k"
    runner = _software_runner()
    args = PerformanceEncoder(runner, settings).default_args()
    assert args[args.index("-b:v") + 1] == "5M"
    assert args[args.index("-b:a") + 1] == "256k"
    assert "-crf" not in args


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


# --------------------------------------------------------------------------- #
# Pipeline profile: end-to-end workflow benchmark through the real runner.
# --------------------------------------------------------------------------- #


class _FakePipelineProcessor:
    """Records step invocations and copies bytes, standing in for FFmpeg work."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _write(self, name: str, source, output) -> None:
        self.calls.append(name)
        Path(output).write_bytes(Path(source).read_bytes())

    def trim(self, source, output, **options): self._write("trim", source, output)
    def resize(self, source, output, *args, **options): self._write("resize", source, output)
    def inspect(self, source): return SimpleNamespace(width=1920, height=1080)


def _pipeline_settings(tmp_path):
    settings = load_config("settings.yaml")
    settings.pipeline.workspace = str(tmp_path / "workspace")
    settings.pipeline.cleanup = True
    return settings


def _clock(values):
    """A ResourceMonitor stand-in whose snapshots yield scripted wall times."""
    monitor = MagicMock()
    monitor.snapshot.side_effect = [SimpleNamespace(wall_time=v, cpu_time=0.0, memory_bytes=1000) for v in values]
    return monitor


def test_pipeline_timeline_aggregates_step_and_bucket_times():
    # Scripted wall clock: pipeline start, start/end for four steps, then complete.
    timeline = PipelineTimeline(monitor=_clock([0.0, 0.0, 0.5, 0.5, 1.0, 1.0, 4.0, 4.0, 4.1, 4.1]))
    timeline("pipeline_started", None)
    for name in ("source", "resize", "encode", "export"):
        timeline("step_started", None, StepRecord(name=name, status="running"))
        timeline("step_completed", None, StepRecord(name=name, status="completed"))
    timeline("pipeline_completed", None)

    steps = timeline.step_timings(origin=0.0)
    assert [s.name for s in steps] == ["source", "resize", "encode", "export"]
    assert steps[2].name == "encode" and steps[2].duration == 3.0
    buckets = timeline.bucket_times(origin=0.0, ended=4.5)
    assert buckets["encoding"] == 3.0          # encode step
    assert buckets["export"] == 0.1            # export step
    assert buckets["processing"] == 1.0        # source (0.5) + resize (0.5)
    assert buckets["cleanup"] == pytest.approx(0.4)  # ended (4.5) - pipeline_completed (4.1)


def _pipeline_benchmark(runner, settings, processor, info):
    return PipelineBenchmark(
        PerformanceEncoder(runner, settings), probe=_probe_for(info),
        decoder_detector=DecoderDetector(runner), downloader=SimpleNamespace(), processor=processor,
    )


def test_pipeline_benchmark_runs_through_real_runner(tmp_path):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source-media")
    settings = _pipeline_settings(tmp_path)
    runner = _software_runner()
    processor = _FakePipelineProcessor()
    info = VideoInfo(path=source, width=1920, height=1080, fps=30.0, duration=8.0, codec="h264")
    result = _pipeline_benchmark(runner, settings, processor, info).run(source, duration=5.0)

    assert result.profile is BenchmarkProfile.PIPELINE
    assert result.pipeline_name == "benchmark_pipeline"
    # The synthetic workflow drove the real runner through the processor.
    assert processor.calls == ["trim", "resize", "resize"]  # trim, resize step, encode step
    names = [step.name for step in result.step_results]
    assert names == ["source", "trim", "resize", "encode", "export"]
    # Output lives in a temp dir cleaned up after run(); its size is captured live.
    assert result.metrics.output_size_bytes > 0
    assert result.total_pipeline_time is not None and result.total_pipeline_time >= 0
    assert result.backend is HardwareBackend.SOFTWARE and not result.metrics.hardware_used


def test_pipeline_benchmark_bucket_and_step_totals_are_consistent(tmp_path):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source-media")
    settings = _pipeline_settings(tmp_path)
    info = VideoInfo(path=source, width=1280, height=720, fps=24.0, duration=20.0, codec="h264")
    result = _pipeline_benchmark(_software_runner(), settings, _FakePipelineProcessor(), info).run(source)

    assert result.download_time == 0.0  # no download step in a local-file workflow
    assert result.resolution == "1280x720"  # probed from the produced output
    # Every reported step carries non-negative monotonic timing.
    for step in result.step_results:
        assert step.duration >= 0 and step.end >= step.start
        assert step.status == "completed"


def test_pipeline_benchmark_reuses_workflow_yaml(tmp_path):
    media = tmp_path / "clip.mp4"; media.write_bytes(b"clip")
    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text(
        "name: shorts_pipeline\nsteps:\n"
        f"  - source:\n      path: {media}\n"
        "  - trim:\n      start: 0\n      end: 2\n"
        "  - export:\n      output: out.mp4\n"
    )
    settings = _pipeline_settings(tmp_path)
    info = VideoInfo(path=media, width=1920, height=1080, fps=30.0, duration=10.0, codec="h264")
    result = _pipeline_benchmark(_software_runner(), settings, _FakePipelineProcessor(), info).run(workflow_file)

    assert result.pipeline_name == "shorts_pipeline"
    assert [step.name for step in result.step_results] == ["source", "trim", "export"]


def test_pipeline_benchmark_json_payload_round_trips(tmp_path):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source-media")
    settings = _pipeline_settings(tmp_path)
    info = VideoInfo(path=source, width=1920, height=1080, fps=30.0, duration=6.0, codec="h264")
    result = _pipeline_benchmark(_software_runner(), settings, _FakePipelineProcessor(), info).run(source, duration=3.0)

    payload = json.loads(json.dumps(result.model_dump(mode="json")))
    assert payload["profile"] == "pipeline"
    assert payload["pipeline_name"] == "benchmark_pipeline"
    assert isinstance(payload["step_results"], list) and payload["step_results"][0]["name"] == "source"
    assert payload["encoding_time"] is not None and payload["total_pipeline_time"] is not None


def test_pipeline_benchmark_propagates_step_failure(tmp_path):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source-media")
    settings = _pipeline_settings(tmp_path)
    processor = _FakePipelineProcessor()

    def boom(*args, **kwargs):
        raise RuntimeError("trim exploded")
    processor.trim = boom

    info = VideoInfo(path=source, width=1920, height=1080, fps=30.0, duration=8.0, codec="h264")
    bench = _pipeline_benchmark(_software_runner(), settings, processor, info)
    with pytest.raises(PipelineStepError, match="trim"):
        bench.run(source, duration=2.0)


def test_pipeline_benchmark_reports_hardware_backend(tmp_path, monkeypatch):
    source = tmp_path / "input.mp4"; source.write_bytes(b"source-media")
    settings = _pipeline_settings(tmp_path)
    runner = MagicMock()

    def fake_run(args, **kwargs):
        if "-encoders" in args:
            return " V..... h264_videotoolbox\n V..... libx264", "", 0.01
        if "-decoders" in args:
            return " V..... h264", "", 0.01
        Path(args[-1]).write_bytes(b"encoded")
        return "", "fps=120 speed=4.0x", 0.02
    runner.run.side_effect = fake_run
    monkeypatch.setattr("src.performance.detector.platform.system", lambda: "Darwin")
    monkeypatch.setattr("src.performance.detector.platform.machine", lambda: "arm64")

    info = VideoInfo(path=source, width=1920, height=1080, fps=30.0, duration=8.0, codec="h264")
    result = _pipeline_benchmark(runner, settings, _FakePipelineProcessor(), info).run(source, duration=4.0)
    assert result.backend is HardwareBackend.VIDEOTOOLBOX and result.metrics.hardware_used
