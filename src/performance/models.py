"""Pydantic models exchanged by the performance components."""

from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field


class HardwareBackend(str, Enum):
    VIDEOTOOLBOX = "videotoolbox"
    NVENC = "nvenc"
    QSV = "qsv"
    SOFTWARE = "software"


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


class BenchmarkResult(BaseModel):
    input_file: Path
    output_file: Path
    codec: str
    backend: HardwareBackend
    metrics: PerformanceMetrics
