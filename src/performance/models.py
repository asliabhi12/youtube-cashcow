"""Pydantic models exchanged by the performance components."""

from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field


class HardwareBackend(str, Enum):
    VIDEOTOOLBOX = "videotoolbox"
    NVENC = "nvenc"
    QSV = "qsv"
    SOFTWARE = "software"


class BenchmarkProfile(str, Enum):
    """Benchmark strategies with different scope and intent."""

    ENCODER = "encoder"      # short clip; isolates encoder throughput from decode cost
    TRANSCODE = "transcode"  # full input; measures the complete decode + encode pipeline
    QUALITY = "quality"      # short clip across presets; compares size, time, and fps
    PIPELINE = "pipeline"    # full production workflow via PipelineRunner; measures end-to-end


class HardwareCapabilities(BaseModel):
    platform: str
    machine: str
    backend: HardwareBackend = HardwareBackend.SOFTWARE
    encoders: list[str] = Field(default_factory=list)
    available: bool = False


class EncodingPreset(BaseModel):
    name: str
    codec: str = "h264"
    bitrate: str | None = None
    audio_bitrate: str = "192k"
    pixel_format: str = "yuv420p"
    gop: int = 60
    faststart: bool = True
    threads: str | int = "auto"
    hardware_preferred: bool = True


class EncoderDecision(BaseModel):
    encoder: str
    backend: HardwareBackend
    hardware: bool
    bitrate: str | None = None
    crf: int | None = None
    preset: str | None = None
    pixel_format: str = "yuv420p"
    gop: int = 60
    faststart: bool = True


class PerformanceMetrics(BaseModel):
    duration_seconds: float = Field(ge=0)
    output_size_bytes: int = Field(ge=0)
    average_fps: float | None = None
    encoding_speed: float | None = None
    cpu_percent: float | None = None
    memory_bytes: int | None = None
    encoder: str
    hardware_used: bool


class DecoderInfo(BaseModel):
    """How the input stream is decoded before re-encoding."""

    codec: str | None = None          # input video codec, e.g. "av1"
    decoder: str | None = None        # resolved decoder, e.g. "libdav1d"
    hardware: bool = False            # True when FFmpeg hardware acceleration is active

    @property
    def label(self) -> str:
        if self.hardware:
            return f"Hardware ({self.decoder})" if self.decoder else "Hardware"
        return f"Software ({self.decoder})" if self.decoder else "Software"


class StepTiming(BaseModel):
    """Wall-clock timing for a single workflow step, taken from runner events."""

    name: str
    start: float = Field(ge=0)          # seconds relative to pipeline start
    end: float = Field(ge=0)            # seconds relative to pipeline start
    duration: float = Field(ge=0)       # end - start
    status: str = "completed"           # mirrors StepRecord.status
    error: str | None = None            # populated when the step failed


class BenchmarkResult(BaseModel):
    input_file: Path
    output_file: Path
    codec: str
    backend: HardwareBackend
    metrics: PerformanceMetrics
    # Optional enrichment (defaults keep older callers and reports valid).
    profile: BenchmarkProfile | None = None
    preset: str | None = None
    decoder: DecoderInfo | None = None
    resolution: str | None = None
    input_codec: str | None = None
    input_duration: float | None = None
    # Pipeline-profile enrichment (all optional; unset for encoder/transcode/quality).
    pipeline_name: str | None = None
    step_results: list[StepTiming] | None = None
    total_pipeline_time: float | None = None
    init_time: float | None = None
    download_time: float | None = None
    processing_time: float | None = None
    encoding_time: float | None = None
    export_time: float | None = None
    cleanup_time: float | None = None
    worker_count: int | None = None
