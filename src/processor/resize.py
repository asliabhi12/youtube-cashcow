"""Aspect-aware resize operations and standard output presets."""

from threading import Event
from .encode import execute
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path

PRESETS = {"1080x1920": (1080, 1920), "1920x1080": (1920, 1080), "1080x1080": (1080, 1080), "720p": (1280, 720), "4k": (3840, 2160)}


def resize(runner: FFmpegRunner, source: PathLike, output: PathLike, width: int | None = None, height: int | None = None, *, preset: str | None = None, padding: bool = False, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Resize while preserving aspect ratio, optionally adding letterbox padding."""
    if preset:
        try: width, height = PRESETS[preset.lower()]
        except KeyError as exc: raise ValueError(f"Unknown resize preset: {preset}") from exc
    if not width or not height: raise ValueError("Resize requires width and height or a preset")
    scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease"
    filter_value = f"{scale},pad={width}:{height}:(ow-iw)/2:(oh-ih)/2" if padding else scale
    return execute(runner, ["-i", str(input_path(source)), "-vf", filter_value, *encode], output, progress=progress, cancel_event=cancel_event)
