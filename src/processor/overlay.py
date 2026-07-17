"""Image overlay compositing."""

from threading import Event
from .encode import execute
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path, position


def overlay(runner: FFmpegRunner, source: PathLike, image: PathLike, output: PathLike, x: str | int = 0, y: str | int = 0, *, opacity: float = 1, scale: int | None = None, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Composite a PNG/image over video with optional alpha and width scaling."""
    if not 0 <= opacity <= 1: raise ValueError("Overlay opacity must be between 0 and 1")
    image_filter = f"[1:v]format=rgba,colorchannelmixer=aa={opacity}"
    if scale: image_filter += f",scale={scale}:-1"
    filter_value = f"{image_filter}[logo];[0:v][logo]overlay={position(x)}:{position(y)}"
    return execute(runner, ["-i", str(input_path(source)), "-i", str(input_path(image)), "-filter_complex", filter_value, *encode], output, progress=progress, cancel_event=cancel_event)
