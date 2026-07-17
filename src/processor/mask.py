"""Alpha-mask filter generation, isolated from overlay and compositing logic.

A mask turns part of an overlay transparent so only a shape (a circle, an
ellipse, …) shows through. Each generator returns the *alpha expression* for
FFmpeg's ``geq`` filter — a per-pixel formula over the overlay frame in terms of
``X``/``Y`` (pixel position) and ``W``/``H`` (frame size). :func:`mask_filter`
wraps the chosen expression into a complete ``format=rgba,geq=...`` filter.

The public surface is a registry (:data:`MASK_BUILDERS`): adding ``rectangle``,
``rounded_rectangle``, ``polygon`` or ``alpha`` later means registering one more
builder, with no change to the compositor, the overlay layer, or callers.
"""

from typing import Callable

from .models import MaskConfig

# type name -> function producing a ``geq`` alpha expression (0..255) for a frame.
MaskBuilder = Callable[[MaskConfig], str]
MASK_BUILDERS: dict[str, MaskBuilder] = {}


def register_mask(name: str) -> Callable[[MaskBuilder], MaskBuilder]:
    """Register an alpha-expression builder under a mask type name."""
    def decorator(builder: MaskBuilder) -> MaskBuilder:
        MASK_BUILDERS[name.lower()] = builder
        return builder
    return decorator


def mask_filter(config: MaskConfig) -> str:
    """Return a full FFmpeg filter that stamps ``config`` into a frame's alpha.

    The result runs on a single overlay input and yields an RGBA frame whose
    colour is untouched and whose alpha follows the shape (with feathering and
    optional inversion already applied by the builder).
    """
    builder = MASK_BUILDERS.get(config.type.lower())
    if builder is None:
        raise ValueError(f"Unknown mask type: {config.type!r} (known: {sorted(MASK_BUILDERS)})")
    alpha = builder(config)
    # Preserve colour planes; overwrite alpha with the shape expression.
    return f"format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha}'"


def _radii(config: MaskConfig, *, circle: bool) -> tuple[str, str]:
    """Horizontal/vertical radius expressions for an elliptical shape.

    Explicit ``width``/``height`` win; otherwise the shape fills the frame. A
    circle collapses to a single radius derived from the smaller extent.
    """
    if circle:
        radius = f"({config.width / 2})" if config.width else "(min(W,H)/2)"
        return radius, radius
    rx = f"({config.width / 2})" if config.width else "(W/2)"
    ry = f"({config.height / 2})" if config.height else "(H/2)"
    return rx, ry


def _ellipse_alpha(config: MaskConfig, *, circle: bool) -> str:
    """Feathered (and optionally inverted) alpha for a circle or ellipse.

    Distance is measured in the shape's own normalised space so a single ramp
    handles both axes; feathering converts a pixel radius into that space using
    the smaller radius, and rotation turns the sampling coordinates.
    """
    rx, ry = _radii(config, circle=circle)
    # Sampling coordinates relative to the frame centre, rotated by -rotation so
    # the shape appears rotated by +rotation.
    dx, dy = "(X-W/2)", "(Y-H/2)"
    if config.rotation:
        from math import cos, radians, sin
        c, s = cos(radians(config.rotation)), sin(radians(config.rotation))
        xr = f"({dx}*{c}+{dy}*{s})"
        yr = f"(-{dx}*{s}+{dy}*{c})"
    else:
        xr, yr = dx, dy
    nd = f"sqrt(pow({xr}/{rx},2)+pow({yr}/{ry},2))"  # 1.0 on the boundary
    if config.feather > 0:
        fn = f"({config.feather}/min({rx},{ry}))"  # feather width in normalised units
        inside = f"clip((1-{nd})/{fn},0,1)"
    else:
        inside = f"lte({nd},1)"
    alpha = f"({inside})*255"
    if config.invert:
        alpha = f"255-{alpha}"
    return alpha


@register_mask("circle")
def _circle(config: MaskConfig) -> str:
    return _ellipse_alpha(config, circle=True)


@register_mask("ellipse")
def _ellipse(config: MaskConfig) -> str:
    return _ellipse_alpha(config, circle=False)
