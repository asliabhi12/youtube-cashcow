"""Thumbnail extraction."""

from threading import Event
from .encode import execute
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path


def thumbnail(runner: FFmpegRunner, source: PathLike, output: PathLike, timestamp: float = 0, *, width: int | None = None, height: int | None = None, progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Extract one frame as a local image."""
    args = ["-ss", str(timestamp), "-i", str(input_path(source)), "-frames:v", "1"]
    if width or height: args += ["-vf", f"scale={width or -1}:{height or -1}"]
    return execute(runner, args, output, progress=progress, cancel_event=cancel_event)
