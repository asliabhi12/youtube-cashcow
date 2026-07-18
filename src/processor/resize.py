"""Aspect-aware resize operations and standard output presets."""

from threading import Event
from .encode import execute
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path

PRESETS = {"1080x1920": (1080, 1920), "1920x1080": (1920, 1080), "1080x1080": (1080, 1080), "720p": (1280, 720), "4k": (3840, 2160)}


def resize(runner: FFmpegRunner, source: PathLike, output: PathLike, width: int | None = None, height: int | None = None, *, preset: str | None = None, padding: bool = False, zoom: float = 1.0, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Resize while preserving aspect ratio, optionally padding and centre-zooming.

    ``zoom`` is a centred punch-in applied *after* sizing: the resized frame is
    enlarged and cropped back to the target resolution, so ``zoom=1.15`` fills the
    frame with a 15% zoom. It is deliberately not called ``scale`` to avoid
    shadowing FFmpeg's ``scale`` filter.

    The enlargement is a **cover** transform, not a naive ``iw*zoom``. After
    ``force_original_aspect_ratio=decrease`` the resized frame fits *inside* the
    target box, so for a mismatched aspect (e.g. landscape into a portrait preset)
    it is smaller than the target on one axis and a plain crop back to the target
    would be impossible. The frame is therefore first scaled by a *cover factor*
    ``max(W/iw, H/ih)`` that guarantees it covers the target on both axes, then by
    the user's ``zoom`` on top. Because ``iw``/``ih`` are the resized frame's own
    dimensions at that point in the graph, this computes exactly
    ``cover_factor * user_zoom`` per the algorithm — the frame entering ``crop`` is
    never smaller than the target, for landscape, portrait, or square inputs alike.

    ``zoom=1.0`` (the default) emits no zoom filters, so the graph is byte-identical
    to the pre-zoom implementation. With ``zoom > 1.0`` the pipeline is
    resize -> cover-zoom -> crop -> (optional) pad, so zoom operates on the resized
    image and not on black padding.
    """
    if preset:
        try: width, height = PRESETS[preset.lower()]
        except KeyError as exc: raise ValueError(f"Unknown resize preset: {preset}") from exc
    if not width or not height: raise ValueError("Resize requires width and height or a preset")
    if zoom < 1.0: raise ValueError(f"Resize zoom must be >= 1.0 (got {zoom})")
    parts = [f"scale={width}:{height}:force_original_aspect_ratio=decrease"]
    if zoom > 1.0:
        # Cover factor from the resized frame's own dims (iw/ih); the comma inside
        # max() is escaped so the filtergraph parser keeps it one scale filter.
        cover = f"max({width}/iw\\,{height}/ih)"
        parts.append(f"scale=iw*{cover}*{zoom}:ih*{cover}*{zoom}")
        parts.append(f"crop={width}:{height}")  # centres by default
    if padding:
        parts.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2")
    filter_value = ",".join(parts)
    return execute(runner, ["-i", str(input_path(source)), "-vf", filter_value, *encode], output, progress=progress, cancel_event=cancel_event)
