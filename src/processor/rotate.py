"""Video rotation operations."""

import math
from threading import Event
from .encode import execute
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path


def rotate(runner: FFmpegRunner, source: PathLike, output: PathLike, degrees: float, *, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Rotate video by standard or arbitrary degree amounts."""
    standard = {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}
    filter_value = standard.get(degrees % 360, f"rotate={math.radians(degrees)}:ow=rotw(iw):oh=roth(ih)")
    return execute(runner, ["-i", str(input_path(source)), "-vf", filter_value, *encode], output, progress=progress, cancel_event=cancel_event)
