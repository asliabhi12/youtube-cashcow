"""Export-quality settings for the workflow adapter.

Export qualities are encoder targets (video/audio bitrate) applied to a *clone*
of the engine settings. They flow through ``Processor._encode`` /
``PerformanceEncoder`` unchanged, which honour an explicit ``video_bitrate`` on
every backend, so quality selection needs no engine change.

Editing presets used to live here too; they have been superseded by the
creative-profile system (``app.services.profiles``), which stores each profile
as an editable YAML file. This module now owns only the export-quality catalogue.
"""

from __future__ import annotations

from typing import Any, TypedDict


class PresetOption(TypedDict):
    """UI-facing description of a selectable option."""

    value: str
    label: str
    description: str


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


def list_qualities() -> list[PresetOption]:
    """Return export-quality options, in declaration order."""
    return [
        {"value": slug, "label": entry["label"], "description": entry["description"]}
        for slug, entry in _EXPORT_QUALITIES.items()
    ]


def is_quality(slug: str) -> bool:
    """Whether ``slug`` names a known export quality."""
    return slug in _EXPORT_QUALITIES


def quality_overrides(slug: str) -> dict[str, Any]:
    """Return the encoder overrides for an export quality (copy)."""
    entry = _EXPORT_QUALITIES.get(slug, _EXPORT_QUALITIES[_DEFAULT_QUALITY])
    return dict(entry["overrides"])
