"""Image and text watermark filters."""

from threading import Event
from .encode import execute
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path

POSITIONS = {
    "top_left": ("20", "20"),
    "top_right": ("main_w-overlay_w-20", "20"),
    "bottom_left": ("20", "main_h-overlay_h-20"),
    "bottom_right": ("main_w-overlay_w-20", "main_h-overlay_h-20"),
    "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
}


def image_watermark(runner: FFmpegRunner, source: PathLike, image: PathLike, output: PathLike, *, placement: str = "bottom_right", opacity: float = .7, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Apply an image watermark at a named placement."""
    from .overlay import overlay
    try: x, y = POSITIONS[placement]
    except KeyError as exc: raise ValueError(f"Unknown watermark placement: {placement}") from exc
    return overlay(runner, source, image, output, x, y, opacity=opacity, encode=encode, progress=progress, cancel_event=cancel_event)


def text_watermark(runner: FFmpegRunner, source: PathLike, output: PathLike, text: str, *, placement: str = "bottom_right", opacity: float = .7, font_size: int = 24, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Burn text into frames with basic transparency and named placement."""
    try: x, y = POSITIONS[placement]
    except KeyError as exc: raise ValueError(f"Unknown watermark placement: {placement}") from exc
    escaped = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    filter_value = f"drawtext=text='{escaped}':x={x}:y={y}:fontsize={font_size}:fontcolor=white@{opacity}"
    return execute(runner, ["-i", str(input_path(source)), "-vf", filter_value, *encode], output, progress=progress, cancel_event=cancel_event)
