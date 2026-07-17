"""Audio extraction and replacement operations."""

from threading import Event
from .encode import execute
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path


def extract_audio(runner: FFmpegRunner, source: PathLike, output: PathLike, *, codec: str = "aac", progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    return execute(runner, ["-i", str(input_path(source)), "-vn", "-c:a", codec], output, progress=progress, cancel_event=cancel_event)


def replace_audio(runner: FFmpegRunner, source: PathLike, audio: PathLike, output: PathLike, *, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    return execute(runner, ["-i", str(input_path(source)), "-i", str(input_path(audio)), "-map", "0:v:0", "-map", "1:a:0", *encode], output, progress=progress, cancel_event=cancel_event)


def audio_filter(runner: FFmpegRunner, source: PathLike, output: PathLike, filter_value: str, *, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    return execute(runner, ["-i", str(input_path(source)), "-af", filter_value, *encode], output, progress=progress, cancel_event=cancel_event)
