"""Image overlay compositing and reusable overlay-geometry helpers.

The legacy :func:`overlay` (image-only, opacity + width scale) is unchanged so
watermark and the existing pipeline step keep working. The helpers below are the
isolated positioning/scaling/rotation logic the richer compositor reuses; they
build FFmpeg expressions only and never construct or run a command.
"""

from threading import Event
from .encode import execute
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path, position

# Named anchors -> (x, y) FFmpeg overlay expressions. ``overlay_w``/``overlay_h``
# refer to the (already scaled) overlay; ``main_w``/``main_h`` to the base video.
OVERLAY_POSITIONS = {
    "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
    "top_left": ("0", "0"),
    "top_right": ("main_w-overlay_w", "0"),
    "bottom_left": ("0", "main_h-overlay_h"),
    "bottom_right": ("main_w-overlay_w", "main_h-overlay_h"),
    "top": ("(main_w-overlay_w)/2", "0"),
    "bottom": ("(main_w-overlay_w)/2", "main_h-overlay_h"),
    "left": ("0", "(main_h-overlay_h)/2"),
    "right": ("main_w-overlay_w", "(main_h-overlay_h)/2"),
}


def resolve_position(x: str | int, y: str | int) -> tuple[str, str]:
    """Turn a named anchor or explicit coordinates into overlay x/y expressions.

    A named anchor (``center``, ``top_left`` …) may be given in either argument
    and expands to both coordinates; otherwise each value is used verbatim as a
    pixel offset or FFmpeg expression.
    """
    for value in (x, y):
        if isinstance(value, str) and value.lower() in OVERLAY_POSITIONS:
            return OVERLAY_POSITIONS[value.lower()]
    return position(x), position(y)


def scale_filter(*, width: int | None = None, height: int | None = None) -> str | None:
    """Return a fixed-pixel ``scale`` filter for the overlay, or ``None`` for no resize.

    Explicit ``width``/``height`` set fixed pixels with ``-1`` preserving aspect
    ratio. Fractional ``scale`` no longer lives here: it is a *cover* of the base
    frame and needs the base dimensions, so it is built with :func:`cover_scale2ref`
    which references the base input rather than the overlay's own size.
    """
    if width or height:
        return f"scale={width or -1}:{height or -1}"
    return None


def cover_scale2ref(scale: float) -> str:
    """Return a ``scale2ref`` filter that sizes the overlay to *cover* the frame.

    ``scale`` is a fraction of the **output frame** (the base video), not the
    overlay's original size: ``1.0`` makes the overlay exactly fill the frame,
    ``0.5`` fill a half-sized box, ``2.0`` twice the frame. Aspect ratio is kept
    and the overlay is grown until it fully covers the target box
    (``force_original_aspect_ratio=increase``), so any excess spills past the box
    and is clipped by the later ``overlay`` step — no black borders, no distortion.

    This is a two-input filter: it consumes ``[overlay][base]`` and emits the
    scaled overlay plus an untouched passthrough of the base, which the compositor
    wires up. The base is only read for its dimensions and is not modified.
    """
    if scale <= 0:
        raise ValueError("Overlay scale must be positive")
    # In scale2ref, main_w/main_h are the *overlay* (the stream being scaled) and
    # rw/rh are the *reference* (base) dimensions — so the target frame is rw x rh.
    # force_original_aspect_ratio is ignored by scale2ref, so the cover factor is
    # made explicit: grow the overlay by max(frame_w/overlay_w, frame_h/overlay_h)
    # so its shorter side still fills the frame, then apply the requested fraction.
    cover = "max(rw/main_w,rh/main_h)"
    return f"scale2ref=w='main_w*{scale}*{cover}':h='main_h*{scale}*{cover}'"


def rotate_filter(degrees: float) -> str | None:
    """Return a transparent-background ``rotate`` filter, or ``None`` when flat."""
    if not degrees % 360:
        return None
    from math import radians
    return f"rotate={radians(degrees)}:ow=rotw({radians(degrees)}):oh=roth({radians(degrees)}):c=none"


def overlay(runner: FFmpegRunner, source: PathLike, image: PathLike, output: PathLike, x: str | int = 0, y: str | int = 0, *, opacity: float = 1, scale: int | None = None, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Composite a PNG/image over video with optional alpha and width scaling."""
    if not 0 <= opacity <= 1: raise ValueError("Overlay opacity must be between 0 and 1")
    image_filter = f"[1:v]format=rgba,colorchannelmixer=aa={opacity}"
    if scale: image_filter += f",scale={scale}:-1"
    filter_value = f"{image_filter}[logo];[0:v][logo]overlay={position(x)}:{position(y)}"
    return execute(runner, ["-i", str(input_path(source)), "-i", str(input_path(image)), "-filter_complex", filter_value, *encode], output, progress=progress, cancel_event=cancel_event)
