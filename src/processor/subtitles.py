"""Subtitle burning support for SRT and WebVTT files."""

from threading import Event
from .encode import execute
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path


def burn_subtitles(runner: FFmpegRunner, source: PathLike, subtitle: PathLike, output: PathLike, *, style: str | None = None, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Burn SRT or VTT subtitles, optionally passing ASS force_style syntax."""
    sub = input_path(subtitle)
    if sub.suffix.lower() not in {".srt", ".vtt"}: raise ValueError("Subtitle input must be SRT or VTT")
    escaped = str(sub).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    filter_value = f"subtitles='{escaped}'" + (f":force_style='{style}'" if style else "")
    return execute(runner, ["-i", str(input_path(source)), "-vf", filter_value, *encode], output, progress=progress, cancel_event=cancel_event)
