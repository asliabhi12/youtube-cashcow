"""Pydantic models shared by FFmpeg processing operations."""

from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field, model_validator


class AudioEffect(BaseModel):
    """A single audio transformation, resolved to an FFmpeg ``-af`` fragment.

    ``type`` selects the builder in :mod:`src.processor.audio`; the remaining
    fields are the per-effect knobs. Only the fields relevant to a given ``type``
    are read, so unused ones keep their identity defaults (``gain=0``,
    ``factor=1``, ``semitones=0``) and never emit a filter. Range checks live in
    :meth:`_validate_ranges` so misconfiguration fails with a helpful message
    before any FFmpeg command is built.
    """

    type: str
    semitones: float = Field(default=0, description="Pitch shift in semitones (pitch/deep_voice/chipmunk)")
    gain: float = Field(default=0, description="Gain in dB (volume/bass/treble)")
    factor: float = Field(default=1.0, gt=0, description="Playback speed multiplier (speed)")
    delay: float = Field(default=500, gt=0, description="Echo delay in milliseconds (echo)")
    decay: float = Field(default=0.5, gt=0, le=1, description="Echo decay factor (echo)")

    @model_validator(mode="after")
    def _validate_ranges(self) -> "AudioEffect":
        if self.type in {"volume", "bass", "treble"} and not -60 <= self.gain <= 60:
            raise ValueError(f"{self.type} gain must be between -60 and 60 dB (got {self.gain})")
        if self.type in {"pitch", "deep_voice", "chipmunk"} and not -24 <= self.semitones <= 24:
            raise ValueError(f"pitch semitones must be between -24 and 24 (got {self.semitones})")
        if self.type == "speed" and not 0.5 <= self.factor <= 100:
            raise ValueError(f"speed factor must be between 0.5 and 100 (got {self.factor})")
        return self


class AudioEffectConfig(BaseModel):
    """One or more chained :class:`AudioEffect` steps.

    Accepts both workflow shapes transparently: a single inline effect
    (``{type: normalize}``) and an explicit chain (``{effects: [...]}``). The
    ``before`` validator normalises the single-effect shape into a one-element
    chain so callers only ever see :attr:`effects`.
    """

    effects: list[AudioEffect] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data):
        if isinstance(data, dict) and "effects" not in data:
            return {"effects": [data]}
        return data


class ColorEffectConfig(BaseModel):
    """Color-grading adjustments, resolved to FFmpeg color filters.

    Every field defaults to its identity value so an unset knob emits no filter
    (see :mod:`src.processor.color`). ``brightness``/``contrast``/``saturation``/
    ``gamma`` map to ``eq``; ``hue`` to ``hue``; ``temperature``/``tint`` to
    ``colorbalance``; ``vibrance`` to the ``vibrance`` filter. Ranges mirror what
    the underlying filters accept, with messages that name the offending field.
    """

    brightness: float = Field(default=0.0, ge=-1.0, le=1.0, description="eq brightness offset (-1..1)")
    contrast: float = Field(default=1.0, ge=0.0, le=3.0, description="eq contrast multiplier (0..3)")
    saturation: float = Field(default=1.0, ge=0.0, le=3.0, description="eq saturation multiplier (0..3)")
    gamma: float = Field(default=1.0, gt=0.0, le=10.0, description="eq gamma (0..10)")
    hue: float = Field(default=0.0, ge=-360.0, le=360.0, description="hue rotation in degrees")
    temperature: float = Field(default=0.0, ge=-1.0, le=1.0, description="warm(+)/cool(-) shift (-1..1)")
    tint: float = Field(default=0.0, ge=-1.0, le=1.0, description="green(+)/magenta(-) shift (-1..1)")
    vibrance: float = Field(default=0.0, ge=-2.0, le=2.0, description="vibrance intensity (-2..2)")


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
    without it the whole (scaled, rotated) overlay is composited. ``color`` is an
    optional grade applied to the overlay pixels *before* compositing, so only
    the overlay is recoloured and the base video is untouched.
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
    color: Optional[ColorEffectConfig] = None

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
