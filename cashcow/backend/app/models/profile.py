"""Request/response schemas for creative profiles.

A *profile* is a reusable bundle of creative parameters — resize, audio, colour,
and overlay settings — that the workflow adapter injects into the fixed
processing pipeline. Profiles never describe workflow steps or their order; they
only supply the options the existing engine steps already accept.

Every field range here mirrors the engine's own validation
(``src/processor/models.py`` and the step option parsers) so the API rejects
anything the engine would reject *before* a job runs, rather than failing
mid-pipeline. Parameters the engine does not implement are intentionally absent.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_METADATA_PROMPT = (
    "Write a clear, searchable YouTube title and description with clean SEO, "
    "natural language, and accurate tags."
)

# --- Resize ---------------------------------------------------------------

# Named platform presets plus dimensional shorthands the engine's resize step
# and processor accept (src/pipeline/steps/resize.py, src/processor/resize.py).
ResizePreset = Literal[
    "youtube",
    "shorts",
    "tiktok",
    "instagram",
    "1080x1920",
    "1920x1080",
    "1080x1080",
    "720p",
    "4k",
]


class ResizeConfig(BaseModel):
    """Resize options. Either a ``preset`` or an explicit ``width``+``height``.

    ``zoom`` is a centred punch-in (>= 1.0; 1.0 is a no-op) and ``padding``
    letterboxes to the target instead of cropping.
    """

    model_config = ConfigDict(extra="forbid")

    preset: ResizePreset | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    zoom: float | None = Field(default=None, ge=1.0)
    padding: bool | None = None

    @model_validator(mode="after")
    def _preset_or_dimensions(self) -> "ResizeConfig":
        has_dims = self.width is not None and self.height is not None
        if self.preset is None and not has_dims:
            raise ValueError("resize requires 'preset' or both 'width' and 'height'")
        return self


# --- Audio ----------------------------------------------------------------

AudioEffectType = Literal[
    "normalize",
    "volume",
    "bass",
    "treble",
    "speed",
    "pitch",
    "deep_voice",
    "chipmunk",
    "echo",
]

# Which optional parameters each effect type accepts. An effect carrying a
# parameter its type does not use is almost always a mistake, so it is rejected
# up front. ``normalize`` takes none.
_AUDIO_TYPE_FIELDS: dict[str, set[str]] = {
    "normalize": set(),
    "volume": {"gain"},
    "bass": {"gain"},
    "treble": {"gain"},
    "speed": {"factor"},
    "pitch": {"semitones"},
    "deep_voice": {"semitones"},
    "chipmunk": {"semitones"},
    "echo": {"delay", "decay"},
}


class AudioEffectItem(BaseModel):
    """A single audio effect in a chain.

    Only the parameters relevant to the effect's ``type`` may be set; ranges
    match the engine's ``AudioEffect`` validation (src/processor/models.py).
    """

    model_config = ConfigDict(extra="forbid")

    type: AudioEffectType
    gain: float | None = Field(default=None, ge=-60, le=60)  # volume/bass/treble, dB
    factor: float | None = Field(default=None, ge=0.5, le=100)  # speed
    semitones: float | None = Field(default=None, ge=-24, le=24)  # pitch/deep_voice/chipmunk
    delay: float | None = Field(default=None, gt=0)  # echo, milliseconds
    decay: float | None = Field(default=None, gt=0, le=1)  # echo

    @model_validator(mode="after")
    def _fields_match_type(self) -> "AudioEffectItem":
        allowed = _AUDIO_TYPE_FIELDS[self.type]
        provided = {
            name
            for name in ("gain", "factor", "semitones", "delay", "decay")
            if getattr(self, name) is not None
        }
        extra = provided - allowed
        if extra:
            raise ValueError(
                f"audio effect '{self.type}' does not accept {sorted(extra)}"
            )
        return self


class AudioConfig(BaseModel):
    """A chain of audio effects, applied in order."""

    model_config = ConfigDict(extra="forbid")

    effects: list[AudioEffectItem] = Field(default_factory=list)


# --- Colour ---------------------------------------------------------------


class ColorConfig(BaseModel):
    """Global colour grade. Every field defaults to its identity value, so a
    grade left at defaults emits no filters (the engine skips it entirely).

    Ranges mirror ``ColorEffectConfig`` (src/processor/models.py). Note the
    engine implements no exposure or sharpen, so neither is exposed here.
    """

    model_config = ConfigDict(extra="forbid")

    brightness: float = Field(default=0.0, ge=-1.0, le=1.0)
    contrast: float = Field(default=1.0, ge=0.0, le=3.0)
    saturation: float = Field(default=1.0, ge=0.0, le=3.0)
    gamma: float = Field(default=1.0, ge=0.0, le=10.0)
    hue: float = Field(default=0.0, ge=-360.0, le=360.0)
    temperature: float = Field(default=0.0, ge=-1.0, le=1.0)
    tint: float = Field(default=0.0, ge=-1.0, le=1.0)
    vibrance: float = Field(default=0.0, ge=-2.0, le=2.0)


# --- Overlay --------------------------------------------------------------

# Named position anchors the engine accepts for x and/or y
# (src/processor/overlay.py). Numeric pixel offsets are also allowed.
OverlayAnchor = Literal[
    "center",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
    "top",
    "bottom",
    "left",
    "right",
]

# Only ``circle`` and ``ellipse`` are registered in the engine's mask builder
# (src/processor/mask.py); other shapes would raise "Unknown mask type".
MaskType = Literal["circle", "ellipse"]


class MaskConfig(BaseModel):
    """Overlay mask. Omit the whole block to skip masking (there is no 'none'
    type). ``invert`` keeps the region *outside* the shape instead of inside.
    """

    model_config = ConfigDict(extra="forbid")

    type: MaskType
    feather: float = Field(default=0.0, ge=0.0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    rotation: float = 0.0
    invert: bool = False


class OverlayConfig(BaseModel):
    """Image or video overlay compositing options.

    ``asset`` is a bare filename resolved against ``assets/overlays/`` by the
    adapter — the API never handles absolute paths. ``scale`` and
    ``width``/``height`` are mutually exclusive (the engine rejects both).
    """

    model_config = ConfigDict(extra="forbid")

    asset: str = Field(min_length=1)
    x: int | OverlayAnchor = "center"
    y: int | OverlayAnchor = "center"
    scale: float | None = Field(default=None, gt=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    rotation: float = 0.0
    layer: int = 0
    color: ColorConfig | None = None
    mask: MaskConfig | None = None

    @model_validator(mode="after")
    def _scale_xor_dimensions(self) -> "OverlayConfig":
        if self.scale is not None and (self.width is not None or self.height is not None):
            raise ValueError("overlay accepts either 'scale' or 'width'/'height', not both")
        return self

    @model_validator(mode="after")
    def _asset_is_bare_filename(self) -> "OverlayConfig":
        # The adapter only ever joins this to assets/overlays/, so a path
        # separator would be either a mistake or a traversal attempt.
        if "/" in self.asset or "\\" in self.asset:
            raise ValueError("overlay 'asset' must be a bare filename, not a path")
        return self


# --- Profile --------------------------------------------------------------


class ProfileInput(BaseModel):
    """Editable profile fields — the body of POST /profiles and PUT /profiles/{id}.

    A creative section left unset means that step is skipped for the profile
    (matching the adapter's ``if "resize" in config`` gating). ``metadata_prompt``
    guides AI metadata generation for jobs created with the profile.
    ``export_quality`` is an optional default the Home page pre-selects and may
    override per job.
    """

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    description: str = ""
    resize: ResizeConfig | None = None
    audio: AudioConfig | None = None
    color: ColorConfig | None = None
    overlay: OverlayConfig | None = None
    metadata_prompt: str = Field(default=DEFAULT_METADATA_PROMPT, min_length=1)
    # Validated against presets.is_quality() at the service layer, where the
    # quality catalogue lives; kept as a plain string here to avoid a cycle.
    export_quality: str | None = None


class Profile(ProfileInput):
    """A stored profile, as returned by the API."""

    id: str
    # True for bundled read-only profiles, False for user-created ones.
    builtin: bool


class ProfileSummary(BaseModel):
    """Lightweight profile entry for the selector list."""

    id: str
    label: str
    description: str
    builtin: bool
