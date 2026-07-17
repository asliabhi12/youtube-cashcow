"""Small validation and FFmpeg argument helpers."""

from pathlib import Path
from typing import Union

from .exceptions import InvalidMediaError

PathLike = Union[str, Path]


def input_path(value: PathLike) -> Path:
    """Resolve and validate an existing, non-empty local input file."""
    path = Path(value).expanduser().resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise InvalidMediaError(f"Input media file is missing or empty: {path}")
    return path


def output_path(value: PathLike) -> Path:
    """Resolve an output path and create its parent directory."""
    path = Path(value).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def fps_value(value: str | None) -> float | None:
    """Convert FFprobe's rational frame-rate representation to a float."""
    if not value or value in {"0/0", "N/A"}:
        return None
    numerator, denominator = value.split("/", 1)
    return float(numerator) / float(denominator)


def position(value: str | int | float) -> str:
    """Format an FFmpeg overlay coordinate without quoting shell syntax."""
    return str(value)
