"""Shared encoding arguments and execution helpers."""

from threading import Event

from .models import ProcessingResult
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, output_path


CODECS = {"h264": "libx264", "h265": "libx265", "av1": "libaom-av1"}
PRESETS = {
    "youtube": ("libx264", "medium", "23"),
    "shorts": ("libx264", "medium", "23"),
    "tiktok": ("libx264", "medium", "23"),
    "instagram": ("libx264", "medium", "23"),
}


def encoding_args(codec: str, preset: str, crf: int, audio_codec: str) -> list[str]:
    """Return consistent encode options for file-producing operations."""
    return ["-c:v", CODECS.get(codec, codec), "-preset", preset, "-crf", str(crf), "-c:a", audio_codec]


def execute(
    runner: FFmpegRunner, args: list[str], output: PathLike, *, progress: ProgressCallback | None = None,
    cancel_event: Event | None = None,
) -> ProcessingResult:
    """Run FFmpeg and ensure its declared output was actually created."""
    target = output_path(output)
    stdout, stderr, elapsed = runner.run([*args, "-y", str(target)], progress=progress, cancel_event=cancel_event)
    if not target.is_file() or target.stat().st_size == 0:
        from .exceptions import ProcessingFailedError
        raise ProcessingFailedError(f"FFmpeg completed but did not create a valid output: {target}")
    return ProcessingResult(output_file=target, duration=elapsed, command=[runner.executable, *args, "-y", str(target)], stderr=stderr)
