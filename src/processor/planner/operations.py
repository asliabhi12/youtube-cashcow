"""Declarative render operations representing individual media transformations.

Each operation is a lightweight, immutable data descriptor that knows how to generate
its specific video and/or audio filter nodes for FFmpeg filter graphs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(kw_only=True)
class RenderOperation(ABC):
    """Abstract base class for all single-pass render operations."""

    type: str = ""
    step_name: str = ""

    @abstractmethod
    def to_video_filters(self) -> list[str]:
        """Return a list of FFmpeg video filter strings for this operation."""
        return []

    @abstractmethod
    def to_audio_filters(self) -> list[str]:
        """Return a list of FFmpeg audio filter strings for this operation."""
        return []

    def get_extra_inputs(self) -> list[Path]:
        """Return additional input media files required by this operation (e.g. overlays)."""
        return []


@dataclass(kw_only=True)
class TrimOperation(RenderOperation):
    """Trim media to a start and end time range in seconds."""

    start: float
    end: float
    type: str = "trim"
    step_name: str = "trim"

    def to_video_filters(self) -> list[str]:
        return [f"trim=start={self.start}:end={self.end}", "setpts=PTS-STARTPTS"]

    def to_audio_filters(self) -> list[str]:
        return [f"atrim=start={self.start}:end={self.end}", "asetpts=PTS-STARTPTS"]


@dataclass(kw_only=True)
class ResizeOperation(RenderOperation):
    """Scale video to target width/height with optional zoom or aspect ratio padding."""

    width: int
    height: int
    zoom: float = 1.0
    type: str = "resize"
    step_name: str = "resize"

    def to_video_filters(self) -> list[str]:
        w, h = self.width, self.height
        if self.zoom > 1.0:
            scale_w = int(w * self.zoom)
            scale_h = int(h * self.zoom)
            crop_x = (scale_w - w) // 2
            crop_y = (scale_h - h) // 2
            return [
                f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase",
                f"crop={w}:{h}:{crop_x}:{crop_y}",
            ]
        return [
            f"scale={w}:{h}:force_original_aspect_ratio=decrease",
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
        ]

    def to_audio_filters(self) -> list[str]:
        return []


@dataclass(kw_only=True)
class CropOperation(RenderOperation):
    """Crop video rectangle."""

    width: int
    height: int
    x: int = 0
    y: int = 0
    type: str = "crop"
    step_name: str = "crop"

    def to_video_filters(self) -> list[str]:
        return [f"crop={self.width}:{self.height}:{self.x}:{self.y}"]

    def to_audio_filters(self) -> list[str]:
        return []


@dataclass(kw_only=True)
class RotateOperation(RenderOperation):
    """Rotate video by specified degrees."""

    degrees: float
    type: str = "rotate"
    step_name: str = "rotate"

    def to_video_filters(self) -> list[str]:
        rad = self.degrees * 3.141592653589793 / 180.0
        return [f"rotate={rad:.6f}:ow=rotw({rad:.6f}):oh=roth({rad:.6f})"]

    def to_audio_filters(self) -> list[str]:
        return []


@dataclass(kw_only=True)
class ColorOperation(RenderOperation):
    """Apply color adjustments (brightness, contrast, saturation, gamma, hue)."""

    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    gamma: float = 1.0
    hue: float = 0.0
    temperature: float = 0.0
    tint: float = 0.0
    vibrance: float = 0.0
    raw_config: Any | None = None
    type: str = "color"
    step_name: str = "color_effect"

    def to_video_filters(self) -> list[str]:
        eq_parts = []
        if self.brightness != 0.0:
            eq_parts.append(f"brightness={self.brightness}")
        if self.contrast != 1.0:
            eq_parts.append(f"contrast={self.contrast}")
        if self.saturation != 1.0:
            eq_parts.append(f"saturation={self.saturation}")
        if self.gamma != 1.0:
            eq_parts.append(f"gamma={self.gamma}")

        filters = []
        if eq_parts:
            filters.append("eq=" + ":".join(eq_parts))
        if self.hue != 0.0:
            filters.append(f"hue=h={self.hue}")
        return filters

    def to_audio_filters(self) -> list[str]:
        return []


@dataclass(kw_only=True)
class AudioOperation(RenderOperation):
    """Apply audio effects (volume, normalize, mute, pitch, tempo)."""

    effects: list[dict[str, Any]] = field(default_factory=list)
    raw_config: Any | None = None
    type: str = "audio"
    step_name: str = "audio_effect"

    def to_video_filters(self) -> list[str]:
        return []

    def to_audio_filters(self) -> list[str]:
        filters = []
        for eff in self.effects:
            eff_type = eff.get("type")
            if eff_type == "volume":
                gain = eff.get("gain", 0.0)
                if gain != 0.0:
                    filters.append(f"volume={gain}dB")
            elif eff_type == "mute":
                filters.append("volume=0")
            elif eff_type == "normalize":
                filters.append("loudnorm")
            elif eff_type == "pitch":
                semitones = eff.get("semitones", 0.0)
                if semitones != 0.0:
                    rate_factor = 2.0 ** (semitones / 12.0)
                    filters.append(f"asetrate=44100*{rate_factor:.4f},aresample=44100")
            elif eff_type == "speed":
                factor = eff.get("factor", 1.0)
                if factor != 1.0:
                    filters.append(f"atempo={factor:.4f}")
        return filters


@dataclass(kw_only=True)
class OverlayOperation(RenderOperation):
    """Overlay an image or video asset onto the primary video stream."""

    source: Path
    x: str | int = 0
    y: str | int = 0
    opacity: float = 1.0
    scale: float | None = None
    width: int | None = None
    height: int | None = None
    rotation: float = 0.0
    mask: Any | None = None
    color: Any | None = None
    is_legacy: bool = False
    legacy_options: dict[str, Any] = field(default_factory=dict)
    raw_config: Any | None = None
    type: str = "overlay"
    step_name: str = "overlay"

    def get_extra_inputs(self) -> list[Path]:
        return [Path(self.source)]

    def to_video_filters(self) -> list[str]:
        return []

    def to_audio_filters(self) -> list[str]:
        return []


@dataclass(kw_only=True)
class WatermarkOperation(RenderOperation):
    """Apply text or image watermark."""

    image_file: Path | None = None
    text: str | None = None
    x: str | int = 10
    y: str | int = 10
    fontsize: int = 24
    fontcolor: str = "white"
    type: str = "watermark"
    step_name: str = "watermark"

    def get_extra_inputs(self) -> list[Path]:
        if self.image_file:
            return [Path(self.image_file)]
        return []

    def to_video_filters(self) -> list[str]:
        if self.text:
            escaped_text = self.text.replace(":", "\\:").replace("'", "'\\\\''")
            return [f"drawtext=text='{escaped_text}':x={self.x}:y={self.y}:fontsize={self.fontsize}:fontcolor={self.fontcolor}"]
        return []

    def to_audio_filters(self) -> list[str]:
        return []


@dataclass(kw_only=True)
class SubtitleOperation(RenderOperation):
    """Burn subtitles into the video stream."""

    file: Path
    type: str = "subtitles"
    step_name: str = "subtitles"

    def to_video_filters(self) -> list[str]:
        escaped_path = str(self.file).replace("\\", "/").replace(":", "\\:")
        return [f"subtitles='{escaped_path}'"]

    def to_audio_filters(self) -> list[str]:
        return []


@dataclass(kw_only=True)
class ConcatOperation(RenderOperation):
    """Concatenate multiple media files."""

    files: list[Path]
    type: str = "concat"
    step_name: str = "concat"

    def get_extra_inputs(self) -> list[Path]:
        return [Path(f) for f in self.files]

    def to_video_filters(self) -> list[str]:
        return []

    def to_audio_filters(self) -> list[str]:
        return []


@dataclass(kw_only=True)
class EncodeOperation(RenderOperation):
    """Specify output video encoding profile/quality parameters."""

    profile: str | None = None
    type: str = "encode"
    step_name: str = "encode"

    def to_video_filters(self) -> list[str]:
        return []

    def to_audio_filters(self) -> list[str]:
        return []
