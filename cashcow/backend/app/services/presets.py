"""Creative presets and export-quality settings for the workflow adapter.

This module is the single source of truth for the two things the UI lets a user
configure without ever touching the fixed processing pipeline:

* **Editing presets** — named bundles of *creative* parameters (resize zoom,
  audio effects, colour grade, overlay). Each preset is a plain declarative
  config that the workflow adapter injects into the existing engine steps. A
  preset never adds, removes, or reorders steps; it only supplies the options a
  step already accepts. A step is emitted only when the chosen preset provides a
  config block for it, so ``custom`` (an empty config) runs the bare pipeline.

* **Export qualities** — encoder targets (video/audio bitrate) applied to a
  *clone* of the engine settings. They flow through ``Processor._encode`` /
  ``PerformanceEncoder`` unchanged, which honour an explicit ``video_bitrate`` on
  every backend, so quality selection needs no engine change.

The config dicts mirror the option shapes the engine steps already accept
(see ``src/pipeline/steps`` and ``src/processor/models.py``). Overlay carries an
``asset`` filename rather than an absolute path; the adapter resolves it against
the repo's ``assets/overlays`` directory so this module stays path-agnostic.
"""

from __future__ import annotations

from typing import Any, TypedDict


class PresetOption(TypedDict):
    """UI-facing description of a selectable option."""

    value: str
    label: str
    description: str


# --- Editing presets -------------------------------------------------------
#
# Each preset maps a slug to a display label/description and a ``config`` whose
# keys are engine concerns: ``resize`` / ``audio`` / ``color`` / ``overlay``.
# A missing key means that step is skipped for the preset. The option values
# mirror what the engine steps accept, so the adapter can pass them through with
# only overlay-path resolution added.
#
# Note: the engine treats an audio effect ``gain`` of 0 as an identity no-op
# (``src/processor/models.py::AudioEffect``), so bass/treble carry a non-zero
# gain to actually take effect.

_EDITING_PRESETS: dict[str, dict[str, Any]] = {
    "youtube-shorts": {
        "label": "YouTube Shorts",
        "description": "Punchy vertical look: zoomed 9:16, boosted audio, vivid grade, and an overlay.",
        "config": {
            "resize": {"preset": "shorts", "zoom": 1.15},
            "audio": {
                "effects": [
                    {"type": "normalize"},
                    {"type": "bass", "gain": 5},
                    {"type": "treble", "gain": 3},
                    {"type": "volume", "gain": 12},
                    {"type": "speed", "factor": 1.03},
                ]
            },
            "color": {
                "brightness": 0.05,
                "contrast": 1.15,
                "saturation": 1.20,
                "gamma": 1.0,
                "hue": 20,
            },
            "overlay": {
                "asset": "yellow.jpg",
                "position": {"x": "center", "y": "center"},
                "scale": 1.0,
                "opacity": 1.0,
                "color": {"saturation": 1.40, "hue": 20, "brightness": 0.08},
                "mask": {"type": "ellipse", "feather": 60, "invert": True},
            },
        },
    },
    "cinematic": {
        "label": "Cinematic",
        "description": "Filmic grade: gentle contrast, slightly desaturated and warm. Clean audio, no overlay.",
        "config": {
            "audio": {"effects": [{"type": "normalize"}]},
            "color": {
                "brightness": -0.02,
                "contrast": 1.10,
                "saturation": 0.95,
                "gamma": 1.0,
                "temperature": 0.15,
            },
        },
    },
    "gaming": {
        "label": "Gaming",
        "description": "High-energy: sharp, saturated colours, punchy bass, and an overlay.",
        "config": {
            "audio": {
                "effects": [
                    {"type": "normalize"},
                    {"type": "bass", "gain": 6},
                ]
            },
            "color": {
                "brightness": 0.03,
                "contrast": 1.20,
                "saturation": 1.30,
                "gamma": 1.0,
            },
            "overlay": {
                "asset": "yellow.jpg",
                "position": {"x": "center", "y": "center"},
                "scale": 1.0,
                "opacity": 1.0,
                "mask": {"type": "ellipse", "feather": 60, "invert": True},
            },
        },
    },
    "podcast": {
        "label": "Podcast",
        "description": "Minimal visual change; just normalised, clear audio.",
        "config": {
            "audio": {"effects": [{"type": "normalize"}]},
        },
    },
    "custom": {
        "label": "Custom",
        "description": "No creative modifications — runs the base pipeline as-is.",
        "config": {},
    },
}

_DEFAULT_PRESET = "custom"


# --- Export qualities ------------------------------------------------------
#
# Overrides applied to a *clone* of ``Settings.ffmpeg``. ``balanced`` mirrors the
# project's current settings.yaml defaults so it is a true no-op baseline.

_EXPORT_QUALITIES: dict[str, dict[str, Any]] = {
    "best": {
        "label": "Best Quality",
        "description": "Highest bitrate; largest file.",
        "overrides": {"video_bitrate": "8000k", "audio_bitrate": "256k"},
    },
    "balanced": {
        "label": "Balanced",
        "description": "A good middle ground of quality and size.",
        "overrides": {"video_bitrate": "4000k", "audio_bitrate": "192k"},
    },
    "small": {
        "label": "Small File",
        "description": "Lower bitrate; smallest file.",
        "overrides": {"video_bitrate": "1500k", "audio_bitrate": "128k"},
    },
}

_DEFAULT_QUALITY = "balanced"


def list_presets() -> list[PresetOption]:
    """Return editing presets as UI options, in declaration order."""
    return [
        {"value": slug, "label": entry["label"], "description": entry["description"]}
        for slug, entry in _EDITING_PRESETS.items()
    ]


def list_qualities() -> list[PresetOption]:
    """Return export-quality options, in declaration order."""
    return [
        {"value": slug, "label": entry["label"], "description": entry["description"]}
        for slug, entry in _EXPORT_QUALITIES.items()
    ]


def is_preset(slug: str) -> bool:
    """Whether ``slug`` names a known editing preset."""
    return slug in _EDITING_PRESETS


def is_quality(slug: str) -> bool:
    """Whether ``slug`` names a known export quality."""
    return slug in _EXPORT_QUALITIES


def preset_config(slug: str) -> dict[str, Any]:
    """Return a deep copy of the preset's creative config.

    Unknown slugs fall back to the default (``custom``) so a caller can never
    crash on a bad value; the route layer validates and rejects unknown slugs
    up front, this is just defence in depth. A copy is returned so callers may
    freely mutate (e.g. inject the resolved overlay path) without corrupting the
    module-level definitions.
    """
    import copy

    entry = _EDITING_PRESETS.get(slug, _EDITING_PRESETS[_DEFAULT_PRESET])
    return copy.deepcopy(entry["config"])


def quality_overrides(slug: str) -> dict[str, Any]:
    """Return the encoder overrides for an export quality (copy)."""
    entry = _EXPORT_QUALITIES.get(slug, _EXPORT_QUALITIES[_DEFAULT_QUALITY])
    return dict(entry["overrides"])
