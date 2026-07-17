"""Pydantic models shared by FFmpeg processing operations."""

from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field, model_validator


class MaskConfig(BaseModel):
    """A shape used to cut the visible region of an overlay.

    ``type`` selects the generator (see :mod:`src.processor.mask`); ``circle``
    and ``ellipse`` ship today, but the registry is open for ``rectangle``,
    ``rounded_rectangle``, ``polygon`` and ``alpha`` without touching callers.
    ``width``/``height`` are the shape's pixel size within the overlay frame;
    when omitted the shape fills the overlay. ``feather`` softens the edge over
    that many pixels, ``rotation`` turns the shape, and ``invert`` keeps the
    outside instead of the inside.
    """

    type: str = "circle"
    feather: float = Field(default=0, ge=0)
    width: Optional[int] = Field(default=None, gt=0)
    height: Optional[int] = Field(default=None, gt=0)
    rotation: float = 0
    invert: bool = False


class OverlayConfig(BaseModel):
    """A single image or video layer composited over the base video.

    Positioning accepts named anchors (``center``, ``top_left`` …) or explicit
    pixel coordinates; ``scale`` is a fraction of the base width, ``opacity`` an
    alpha multiplier, ``rotation`` a clockwise degree turn, and ``layer`` an
    ordering hint for callers that stack several overlays. ``mask`` is optional;
    without it the whole (scaled, rotated) overlay is composited.
    """

    source: Path
    x: Union[int, str] = "center"
    y: Union[int, str] = "center"
    scale: Optional[float] = Field(default=None, gt=0)
    width: Optional[int] = Field(default=None, gt=0)
    height: Optional[int] = Field(default=None, gt=0)
    opacity: float = Field(default=1.0, ge=0, le=1)
    rotation: float = 0
    layer: int = 0
    mask: Optional[MaskConfig] = None

    @model_validator(mode="after")
    def _one_scaling_mode(self) -> "OverlayConfig":
        if self.scale is not None and (self.width is not None or self.height is not None):
            raise ValueError("overlay accepts either 'scale' or explicit width/height, not both")
        return self


class VideoInfo(BaseModel):
    """Typed media details reported by FFprobe."""

    path: Path
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    duration: Optional[float] = None
    bitrate: Optional[int] = None
    codec: Optional[str] = None
    audio_codec: Optional[str] = None
    has_audio: bool = False


class ProcessingResult(BaseModel):
    """Successful FFmpeg operation output and execution details."""

    output_file: Path
    duration: float = Field(ge=0)
    command: list[str]
    stderr: str = ""
