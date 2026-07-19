"""Export-quality option route.

The frontend fetches this list to render the export-quality radio group, keeping
the backend the single source of truth for the option set (labels, descriptions,
and slugs) that ``POST /jobs`` validates. Editing presets have been replaced by
the creative-profile system; see ``app.api.profiles``.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.presets import list_qualities

router = APIRouter(tags=["presets"])


class PresetOption(BaseModel):
    """A selectable option for the UI (export quality)."""

    value: str
    label: str
    description: str


@router.get("/export-qualities", response_model=list[PresetOption])
def get_export_qualities() -> list[PresetOption]:
    """Return the available export-quality options, in display order."""
    return [PresetOption(**option) for option in list_qualities()]
