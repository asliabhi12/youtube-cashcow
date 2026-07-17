"""Compare real hardware and software encodes using the existing runner.

The benchmark orchestrates the performance encoder, FFprobe, and decode-path
detection. It performs no FFmpeg execution of its own: every command still runs
through ``FFmpegRunner`` via ``PerformanceEncoder`` and ``FFprobe``.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from .decoder import DecoderDetector
from .encoder import PerformanceEncoder
from .models import BenchmarkProfile, BenchmarkResult, DecoderInfo, PerformanceMetrics
from .pipeline_benchmark import PipelineBenchmark
from .profiler import EncodingProfiler
from src.processor.ffprobe import FFprobe
from src.processor.models import VideoInfo

# Curated presets compared by the quality profile: they vary bitrate and codec,
# yielding meaningful size / time / fps differences.
QUALITY_PRESETS: tuple[str, ...] = ("youtube_1080", "youtube_4k", "archive")

# Default clip length (seconds) for encoder and quality profiles.
DEFAULT_CLIP_SECONDS = 30.0


class Benchmark:
    """Produce comparable, typed reports for a local media input."""

    def __init__(self, encoder: PerformanceEncoder, probe: FFprobe | None = None, decoder_detector: DecoderDetector | None = None, processor=None) -> None:
        self.encoder = encoder
        self._probe = probe
        self._detector = decoder_detector
        self._processor = processor
        self._pipeline: PipelineBenchmark | None = None

    @classmethod
    def from_processor(cls, processor) -> "Benchmark":
        return cls(PerformanceEncoder.from_processor(processor), probe=processor.probe, processor=processor)

    @property
    def probe(self) -> FFprobe:
        if self._probe is None:
            self._probe = FFprobe(self.encoder.settings.ffmpeg.ffprobe, self.encoder.runner.logger)
        return self._probe

    @property
    def detector(self) -> DecoderDetector:
        if self._detector is None:
            self._detector = DecoderDetector(self.encoder.runner)
        return self._detector

    @property
    def pipeline(self) -> PipelineBenchmark:
        if self._pipeline is None:
            self._pipeline = PipelineBenchmark(
                self.encoder, probe=self._probe, decoder_detector=self._detector,
                processor=self._processor,
            )
        return self._pipeline

    def compare(self, input_file: str | Path, *, software: bool = True, hardware: bool = True) -> list[BenchmarkResult]:
        """Backward-compatible full-file hardware/software comparison."""
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

    def run(self, input_file: str | Path, *, profile: BenchmarkProfile = BenchmarkProfile.ENCODER, duration: float | None = None) -> list[BenchmarkResult]:
        """Benchmark ``input_file`` according to ``profile``.

        ``encoder`` isolates encoder throughput on a short clip, ``transcode``
        measures the full decode + encode pipeline, ``quality`` compares several
        presets on the fastest available backend, and ``pipeline`` runs a full
        production workflow through the real PipelineRunner. ``duration``
        overrides the profile's default clip length.
        """
        source = Path(input_file)
        if profile is BenchmarkProfile.PIPELINE:
            # Delegate to the workflow benchmark; it runs the real PipelineRunner
            # and accepts either a media file or a workflow YAML as input.
            return [self.pipeline.run(source, duration=duration)]
        if not source.is_file():
            raise FileNotFoundError(f"Benchmark input does not exist: {source}")
        info = self.probe.inspect(source)
        decoder = self.detector.detect(info.codec, self.encoder.settings.ffmpeg.hwaccel)
        clip = self._clip_duration(profile, duration, info)
        with TemporaryDirectory(prefix="cashcow_benchmark_") as directory:
            root = Path(directory)
            if profile is BenchmarkProfile.QUALITY:
                return self._run_quality(source, root, clip, profile, info, decoder)
            reports: list[BenchmarkResult] = []
            if self.encoder.capabilities.available:
                reports.append(self._run(source, root / "hardware.mp4", False, clip, profile, info, decoder))
            reports.append(self._run(source, root / "software.mp4", True, clip, profile, info, decoder))
            return reports

    def _run_quality(self, source: Path, root: Path, clip: float | None, profile: BenchmarkProfile, info: VideoInfo, decoder: DecoderInfo) -> list[BenchmarkResult]:
        force_software = not self.encoder.capabilities.available
        reports: list[BenchmarkResult] = []
        for name in QUALITY_PRESETS:
            output = root / f"quality_{name}.mp4"
            reports.append(self._run(source, output, force_software, clip, profile, info, decoder, preset=name))
        return reports

    def _run(self, source: Path, output: Path, force_software: bool, duration: float | None = None, profile: BenchmarkProfile | None = None, info: VideoInfo | None = None, decoder: DecoderInfo | None = None, preset: str | None = None) -> BenchmarkResult:
        profiler = EncodingProfiler(); profiler.start()
        decision, stderr, elapsed = self.encoder.encode(source, output, profile=preset, force_software=force_software, duration=duration)
        metrics = profiler.finish(output, decision, stderr, elapsed)
        metrics = self._ensure_speed(metrics, duration, info, elapsed)
        return BenchmarkResult(
            input_file=source, output_file=output, codec=decision.encoder, backend=decision.backend,
            metrics=metrics, profile=profile, preset=preset, decoder=decoder,
            resolution=self._resolution(info), input_codec=info.codec if info else None,
            input_duration=info.duration if info else None,
        )

    @staticmethod
    def _clip_duration(profile: BenchmarkProfile, duration: float | None, info: VideoInfo) -> float | None:
        if duration and duration > 0:
            chosen: float | None = duration
        elif profile is BenchmarkProfile.TRANSCODE:
            chosen = None  # full file
        else:
            chosen = DEFAULT_CLIP_SECONDS
        # Never request more than the source provides; FFmpeg would stop early
        # anyway, but this keeps the reported clip length honest.
        if chosen is not None and info.duration and chosen > info.duration:
            return info.duration
        return chosen

    @staticmethod
    def _ensure_speed(metrics: PerformanceMetrics, duration: float | None, info: VideoInfo | None, elapsed: float) -> PerformanceMetrics:
        """Derive speed (x realtime) when FFmpeg did not report ``speed=``."""
        if metrics.encoding_speed is not None:
            return metrics
        encoded = duration or (info.duration if info else None)
        if encoded and elapsed > 0:
            return metrics.model_copy(update={"encoding_speed": round(encoded / elapsed, 3)})
        return metrics

    @staticmethod
    def _resolution(info: VideoInfo | None) -> str | None:
        if info and info.width and info.height:
            return f"{info.width}x{info.height}"
        return None
