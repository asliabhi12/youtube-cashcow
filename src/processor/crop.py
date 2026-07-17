"""Crop local video frames."""

from threading import Event
from .encode import execute
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path


def crop(runner: FFmpegRunner, source: PathLike, output: PathLike, width: int, height: int, x: int = 0, y: int = 0, *, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Crop a rectangle from each frame."""
    if min(width, height) <= 0:
        from .exceptions import InvalidMediaError
        raise InvalidMediaError("Crop width and height must be positive")
    return execute(runner, ["-i", str(input_path(source)), "-vf", f"crop={width}:{height}:{x}:{y}", *encode], output, progress=progress, cancel_event=cancel_event)
