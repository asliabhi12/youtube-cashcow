"""Preset and export-quality option routes.

The frontend fetches these lists to render the editing-preset selector and the
export-quality radio group, keeping the backend the single source of truth for
the option set (labels, descriptions, and slugs) that ``POST /jobs`` validates.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.presets import list_presets, list_qualities

router = APIRouter(tags=["presets"])


class PresetOption(BaseModel):
    """A selectable option for the UI (preset or export quality)."""

    value: str
    label: str
    description: str


@router.get("/presets", response_model=list[PresetOption])
def get_presets() -> list[PresetOption]:
    """Return the available editing presets, in display order."""
    return [PresetOption(**option) for option in list_presets()]


@router.get("/export-qualities", response_model=list[PresetOption])
def get_export_qualities() -> list[PresetOption]:
    """Return the available export-quality options, in display order."""
    return [PresetOption(**option) for option in list_qualities()]
