"""Masking and compositing orchestration.

The compositor turns an :class:`OverlayConfig` into one FFmpeg ``filter_complex``
that scales, masks, rotates and fades an overlay, then lays it over the base
video. It only *assembles* the command; execution goes through :func:`execute`
and therefore :class:`FFmpegRunner`, keeping the single subprocess boundary
intact. Masking, positioning and geometry each live in their own modules
(:mod:`mask`, :mod:`overlay`), so this file stays a thin coordinator and no shape
logic leaks in here.

Filter order on the overlay input: ``scale -> mask -> rotate -> opacity``. Mask
before rotate means the shape rotates together with the overlay content; opacity
last multiplies whatever alpha the mask produced, so feathering is preserved.
"""

from threading import Event

from .encode import execute
from .mask import mask_filter
from .models import OverlayConfig
from .overlay import cover_scale2ref, resolve_position, rotate_filter, scale_filter
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path


def _effects_chain(config: OverlayConfig) -> str:
    """Build the mask -> rotate -> opacity chain applied to the scaled overlay.

    This runs *after* whatever sizing the overlay received, so masks fill and
    rotation turns the final overlay pixels. It is independent of the scaling
    mode: cover-scaling (``scale2ref``) and fixed-pixel scaling both feed their
    result straight into this chain.
    """
    parts: list[str] = []
    # mask_filter already emits ``format=rgba,geq=...``; without a mask we still
    # need an alpha channel so the opacity multiplier below has something to act on.
    parts.append(mask_filter(config.mask) if config.mask else "format=rgba")
    rotate = rotate_filter(config.rotation)
    if rotate:
        parts.append(rotate)
    parts.append(f"colorchannelmixer=aa={config.opacity}")
    return ",".join(parts)


def _overlay_chain(config: OverlayConfig) -> str:
    """Single-input overlay filter chain: optional fixed-pixel scale, then effects.

    Used for the default (no scaling) and explicit ``width``/``height`` cases,
    where the overlay is sized without reference to the base frame. Fractional
    ``scale`` is a *cover* and does not flow through here — the compositor builds
    it as a two-input ``scale2ref`` node instead (see :func:`composite`).
    """
    parts: list[str] = []
    scale = scale_filter(width=config.width, height=config.height)
    if scale:
        parts.append(scale)
    parts.append(_effects_chain(config))
    return ",".join(parts)


def composite(runner: FFmpegRunner, source: PathLike, config: OverlayConfig, output: PathLike, *,
              encode: list[str], progress: ProgressCallback | None = None,
              cancel_event: Event | None = None):
    """Composite one masked overlay onto ``source`` and write ``output``.

    The base video is always fully visible outside the overlay; only the overlay
    is scaled, masked, feathered, rotated and faded. Image and video overlays are
    handled identically: the ``overlay`` filter drives its output off the base
    input and repeats the overlay's last frame (``eof_action=repeat``), so a
    single-frame image is held for the base's full duration and a shorter video
    overlay freezes on its final frame. The output therefore always matches the
    base's length without needing ``-loop``/``-shortest`` (which would create an
    unbounded image stream and hang the encode).

    Fractional ``scale`` sizes the overlay relative to the *output frame*, not the
    overlay's own dimensions: it is a cover (``scale2ref`` with
    ``force_original_aspect_ratio=increase``) computed from the base's width and
    height, so ``scale=1.0`` fully fills the frame with no black borders and the
    ``overlay`` step clips any spill. Explicit ``width``/``height`` keep their
    fixed-pixel meaning and stay a single-input scale.
    """
    base = input_path(source)
    overlay_source = input_path(config.source)
    x, y = resolve_position(config.x, config.y)
    if config.scale is not None:
        # Cover-scale needs the base frame as a reference, so scale2ref consumes
        # both inputs ([overlay][base]) and emits the sized overlay plus an
        # untouched base passthrough; effects then run on the sized overlay.
        filter_value = (
            f"[1:v][0:v]{cover_scale2ref(config.scale)}[ovs][base];"
            f"[ovs]{_effects_chain(config)}[ov];[base][ov]overlay={x}:{y}"
        )
    else:
        filter_value = f"[1:v]{_overlay_chain(config)}[ov];[0:v][ov]overlay={x}:{y}"
    args = ["-i", str(base), "-i", str(overlay_source), "-filter_complex", filter_value, *encode]
    return execute(runner, args, output, progress=progress, cancel_event=cancel_event)
