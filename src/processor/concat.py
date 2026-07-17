"""Validated concatenation of compatible local videos."""

from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Event

from .encode import execute
from .exceptions import UnsupportedCodecError
from .ffprobe import FFprobe
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path


def concat(runner: FFmpegRunner, probe: FFprobe, sources: list[PathLike], output: PathLike, *, reencode: bool = False, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Join videos after validating codec, dimensions and frame rate for stream-copy."""
    paths = [input_path(item) for item in sources]
    if len(paths) < 2: raise ValueError("Concatenation requires at least two videos")
    details = [probe.inspect(item) for item in paths]
    signatures = {(item.codec, item.width, item.height, item.fps, item.audio_codec) for item in details}
    if len(signatures) > 1 and not reencode:
        raise UnsupportedCodecError("Concat inputs differ in codec, dimensions, fps, or audio codec; use reencode=True")
    list_file = NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False)
    try:
        for path in paths: list_file.write("file '" + str(path).replace("'", "'\\''") + "'\n")
        list_file.close()
        args = ["-f", "concat", "-safe", "0", "-i", list_file.name]
        args += encode if reencode else ["-c", "copy"]
        return execute(runner, args, output, progress=progress, cancel_event=cancel_event)
    finally:
        Path(list_file.name).unlink(missing_ok=True)
