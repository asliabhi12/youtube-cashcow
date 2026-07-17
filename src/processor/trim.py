"""Trim local media files."""

from threading import Event
from .encode import execute, encoding_args
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path


def trim(runner: FFmpegRunner, source: PathLike, output: PathLike, start: float, end: float, *, stream_copy: bool = False, progress: ProgressCallback | None = None, cancel_event: Event | None = None, encode: list[str] | None = None):
    """Create a clip between start and end seconds, accurately unless stream-copying."""
    if start < 0 or end <= start:
        from .exceptions import InvalidMediaError
        raise InvalidMediaError("Trim end must be greater than a non-negative start")
    args = ["-i", str(input_path(source)), "-ss", str(start), "-to", str(end)]
    args += ["-c", "copy"] if stream_copy else (encode or encoding_args("h264", "medium", 23, "aac"))
    return execute(runner, args, output, progress=progress, cancel_event=cancel_event)
