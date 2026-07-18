"""End-to-end workflow benchmark built on the real PipelineRunner.

The pipeline profile answers "how long would a real production workflow take?"
It runs an actual :class:`PipelineRunner`, so every step executes exactly as in
production and all FFmpeg work stays inside ``FFmpegRunner``. Timing is captured
by observing the runner's own progress events rather than re-implementing any
step or timing logic here.
"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from .decoder import DecoderDetector
from .encoder import PerformanceEncoder
from .models import BenchmarkProfile, BenchmarkResult, DecoderInfo, PerformanceMetrics, StepTiming
from .resources import ResourceMonitor
from src.pipeline import PipelineRunner, default_registry
from src.pipeline.models import WorkflowDefinition, WorkflowStep
from src.pipeline.validator import load_workflow
from src.processor.ffprobe import FFprobe
from src.processor.models import VideoInfo

# Default clip length (seconds) for the synthetic workflow, mirroring the
# encoder/quality profiles so a pipeline run stays fast and comparable.
DEFAULT_CLIP_SECONDS = 30.0

# Step name -> timing bucket. Anything unmapped is aggregated as processing.
_BUCKETS = {"download": "download", "encode": "encoding", "export": "export",
            "audio_effect": "audio", "color_effect": "color"}


class PipelineTimeline:
    """A :class:`PipelineRunner` progress callback that records step timing.

    It implements the ``(event, context, record)`` signature the runner already
    emits, stamping ``ResourceMonitor`` wall-clock times at each boundary. No new
    instrumentation is added to the runner; timing is purely observed.
    """

    def __init__(self, monitor: ResourceMonitor | None = None) -> None:
        self.monitor = monitor or ResourceMonitor()
        self.pipeline_started: float | None = None
        self.pipeline_completed: float | None = None
        self.steps: list[dict] = []

    def __call__(self, event: str, context, record=None) -> None:
        now = self.monitor.snapshot().wall_time
        if event == "pipeline_started":
            self.pipeline_started = now
        elif event == "step_started" and record is not None:
            self.steps.append({"name": record.name, "start": now, "end": None, "status": "running", "error": None})
        elif event in {"step_completed", "step_failed"} and record is not None:
            entry = self._open_entry()
            if entry is not None:
                entry.update(end=now, status=record.status, error=record.detail)
        elif event == "pipeline_completed":
            self.pipeline_completed = now

    def _open_entry(self) -> dict | None:
        for entry in reversed(self.steps):
            if entry["end"] is None:
                return entry
        return None

    def step_timings(self, origin: float) -> list[StepTiming]:
        """Per-step timings relative to ``origin`` (the benchmark start)."""
        timings: list[StepTiming] = []
        for entry in self.steps:
            end = entry["end"] if entry["end"] is not None else entry["start"]
            start_rel = max(0.0, round(entry["start"] - origin, 4))
            end_rel = max(start_rel, round(end - origin, 4))
            timings.append(StepTiming(
                name=entry["name"], start=start_rel, end=end_rel,
                duration=round(end_rel - start_rel, 4), status=entry["status"], error=entry["error"],
            ))
        return timings

    def bucket_times(self, origin: float, ended: float) -> dict[str, float]:
        """Aggregate wall time into init/download/processing/encoding/export/cleanup."""
        buckets = {name: 0.0 for name in ("init", "download", "processing", "audio", "color", "encoding", "export", "cleanup")}
        first_start = self.steps[0]["start"] if self.steps else self.pipeline_started
        if first_start is not None:
            buckets["init"] = max(0.0, round(first_start - origin, 4))
        for entry in self.steps:
            end = entry["end"] if entry["end"] is not None else entry["start"]
            key = _BUCKETS.get(entry["name"].lower(), "processing")
            buckets[key] = round(buckets[key] + max(0.0, end - entry["start"]), 4)
        if self.pipeline_completed is not None:
            buckets["cleanup"] = max(0.0, round(ended - self.pipeline_completed, 4))
        return buckets


class PipelineBenchmark:
    """Benchmark a complete workflow through the production PipelineRunner."""

    def __init__(self, encoder: PerformanceEncoder, *, registry=None, probe: FFprobe | None = None,
                 decoder_detector: DecoderDetector | None = None, downloader=None, processor=None) -> None:
        self.encoder = encoder
        self.settings = encoder.settings
        self.registry = registry or default_registry()
        self.downloader = downloader
        self.processor = processor
        self._probe = probe
        self._detector = decoder_detector

    @property
    def probe(self) -> FFprobe:
        if self._probe is None:
            self._probe = FFprobe(self.settings.ffmpeg.ffprobe, self.encoder.runner.logger)
        return self._probe

    @property
    def detector(self) -> DecoderDetector:
        if self._detector is None:
            self._detector = DecoderDetector(self.encoder.runner)
        return self._detector

    def run(self, input_file: str | Path, *, duration: float | None = None) -> BenchmarkResult:
        """Execute a real workflow for ``input_file`` and report end-to-end timing.

        A ``.yaml``/``.yml`` input reuses that workflow definition; a media file
        gets a synthetic ``source -> trim -> resize -> encode -> export`` workflow
        built from the existing Pipeline models. No FFmpeg command is issued here.
        """
        source = Path(input_file)
        is_workflow = source.suffix.lower() in {".yaml", ".yml"}
        with TemporaryDirectory(prefix="cashcow_pipebench_") as tmp:
            export_target = Path(tmp) / "pipeline_output.mp4"
            workflow, media = self._resolve_workflow(source, duration, export_target, is_workflow)
            timeline = PipelineTimeline()
            runner = PipelineRunner(self.settings, self.registry, downloader=self.downloader,
                                    processor=self.processor, progress=timeline)
            filter_graph_time = self._measure_filter_graph(workflow)
            monitor = ResourceMonitor()
            start_snap = monitor.snapshot()
            result = runner.run(workflow)
            end_snap = monitor.snapshot()
            cpu = monitor.cpu_percent(start_snap, end_snap)
            return self._build_result(source, media, result, timeline, start_snap.wall_time,
                                      end_snap.wall_time, duration, cpu, end_snap.memory_bytes,
                                      filter_graph_time)

    @staticmethod
    def _measure_filter_graph(workflow: WorkflowDefinition) -> float:
        """Time filter-graph *generation* for the effect steps (no FFmpeg).

        This isolates the pure-Python cost of turning effect configs into FFmpeg
        filter strings from the encode cost that dominates the wall clock. It
        reuses the exact builders the steps use, so it never duplicates FFmpeg
        logic; unrelated steps contribute nothing.
        """
        from time import perf_counter

        from src.processor.audio import effect_chain
        from src.processor.color import color_chain
        from src.processor.models import AudioEffectConfig, ColorEffectConfig

        started = perf_counter()
        for step in workflow.steps:
            name = step.name.lower()
            try:
                if name == "audio_effect":
                    effect_chain(AudioEffectConfig(**step.options))
                elif name == "color_effect":
                    color_chain(ColorEffectConfig(**step.options))
            except Exception:
                # Generation timing is best-effort; malformed configs are caught
                # by validation during the real run, not here.
                continue
        return round(perf_counter() - started, 6)

    def _resolve_workflow(self, source: Path, duration: float | None, export_target: Path,
                          is_workflow: bool) -> tuple[WorkflowDefinition, Path | None]:
        if is_workflow:
            return load_workflow(source), None
        if not source.is_file():
            raise FileNotFoundError(f"Benchmark input does not exist: {source}")
        return self._synthetic_workflow(source, duration, export_target), source

    def _synthetic_workflow(self, source: Path, duration: float | None, export_target: Path) -> WorkflowDefinition:
        info = self.probe.inspect(source)
        clip = self._clip_end(duration, info)
        # Absolute path so the source step resolves independently of the
        # workflow directory (SourceStep.resolve_path joins relatives to it).
        steps = [WorkflowStep(name="source", options={"path": str(source.resolve())})]
        if clip:
            steps.append(WorkflowStep(name="trim", options={"start": 0, "end": clip}))
        if info.width and info.height:
            steps.append(WorkflowStep(name="resize", options={"width": info.width, "height": info.height}))
        steps.append(WorkflowStep(name="encode", options={}))
        steps.append(WorkflowStep(name="export", options={"output": str(export_target)}))
        return WorkflowDefinition(name="benchmark_pipeline", steps=steps, source_path=source)

    def _build_result(self, source: Path, media: Path | None, result, timeline: PipelineTimeline,
                       started: float, ended: float, duration: float | None, cpu: float, memory: int,
                       filter_graph_time: float = 0.0) -> BenchmarkResult:
        total = round(ended - started, 4)
        buckets = timeline.bucket_times(started, ended)
        output = Path(result.output_file) if result.output_file else None
        out_info = self._safe_probe(output)
        in_info = self._safe_probe(media) if media else out_info
        decision = self.encoder.decision()
        decoder = self.detector.detect(in_info.codec if in_info else None, self.settings.ffmpeg.hwaccel)
        encoded = (out_info.duration if out_info else None) or duration or (in_info.duration if in_info else None)
        speed = round(encoded / buckets["encoding"], 3) if encoded and buckets["encoding"] > 0 else None
        fps = round((out_info.fps or 0) * speed, 2) if speed and out_info and out_info.fps else None
        metrics = PerformanceMetrics(
            duration_seconds=total,
            output_size_bytes=output.stat().st_size if output and output.is_file() else 0,
            average_fps=fps, encoding_speed=speed, cpu_percent=cpu, memory_bytes=memory,
            encoder=decision.encoder, hardware_used=decision.hardware,
        )
        return BenchmarkResult(
            input_file=source, output_file=output or source, codec=decision.encoder,
            backend=decision.backend, metrics=metrics, profile=BenchmarkProfile.PIPELINE,
            decoder=decoder, resolution=self._resolution(out_info),
            input_codec=in_info.codec if in_info else None,
            input_duration=in_info.duration if in_info else None,
            pipeline_name=result.name, step_results=timeline.step_timings(started),
            total_pipeline_time=total, init_time=buckets["init"], download_time=buckets["download"],
            processing_time=buckets["processing"], audio_time=buckets["audio"], color_time=buckets["color"],
            encoding_time=buckets["encoding"], export_time=buckets["export"], cleanup_time=buckets["cleanup"],
            filter_graph_time=filter_graph_time, worker_count=self._worker_count(),
        )

    def _safe_probe(self, media: Path | None) -> VideoInfo | None:
        if not media or not Path(media).is_file():
            return None
        try:
            return self.probe.inspect(media)
        except Exception:
            return None

    def _clip_end(self, duration: float | None, info: VideoInfo) -> float | None:
        chosen = duration if duration and duration > 0 else DEFAULT_CLIP_SECONDS
        if info.duration and chosen > info.duration:
            return round(info.duration, 3)
        return chosen

    def _worker_count(self) -> int:
        workers = self.settings.performance.workers
        if isinstance(workers, int):
            return workers
        return os.cpu_count() or 1

    @staticmethod
    def _resolution(info: VideoInfo | None) -> str | None:
        if info and info.width and info.height:
            return f"{info.width}x{info.height}"
        return None
