"""Color-grading filter generation, isolated from execution and compositing.

A :class:`ColorBuilder` turns a :class:`~.models.ColorEffectConfig` into FFmpeg
filter *fragments* (``eq``, ``hue``, ``colorbalance``, ``vibrance``). It only
builds expression strings; nothing here constructs or runs an FFmpeg command, so
the single subprocess boundary in :mod:`src.processor.runner` stays intact.

The builder is deliberately *identity-aware*: a knob left at its neutral value
(brightness ``0``, contrast/saturation/gamma ``1``, hue/temperature/tint/vibrance
``0``) contributes no fragment, so a no-op grade produces an empty filter chain
and the caller can skip re-encoding entirely. ``eq`` groups its four knobs into a
single node so an all-``eq`` grade is one filter, not four.
"""

from threading import Event

from .encode import execute
from .models import ColorEffectConfig
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path

# eq knob -> (identity value, formatter). Grouped so brightness/contrast/
# saturation/gamma collapse into a single ``eq=`` node instead of four filters.
_EQ_KNOBS = (
    ("brightness", 0.0),
    ("contrast", 1.0),
    ("saturation", 1.0),
    ("gamma", 1.0),
)


def _fmt(value: float) -> str:
    """Render a float compactly (``1.2`` not ``1.2000000001``) for stable graphs."""
    return f"{value:g}"


class ColorBuilder:
    """Assemble reusable FFmpeg color-grade fragments from a config."""

    def __init__(self, config: ColorEffectConfig) -> None:
        self.config = config

    def _eq_fragment(self) -> str | None:
        parts = [f"{name}={_fmt(getattr(self.config, name))}"
                 for name, identity in _EQ_KNOBS if getattr(self.config, name) != identity]
        return f"eq={':'.join(parts)}" if parts else None

    def _hue_fragment(self) -> str | None:
        if self.config.hue == 0:
            return None
        return f"hue=h={_fmt(self.config.hue)}"

    def _balance_fragment(self) -> str | None:
        """Temperature/tint via ``colorbalance`` midtone shifts.

        Temperature is a warm(+)/cool(-) axis: positive lifts red and drops blue;
        tint is a green(+)/magenta(-) axis on the green channel. Both act on
        midtones so skin tones move naturally without clipping shadows/highlights.
        """
        temp, tint = self.config.temperature, self.config.tint
        if temp == 0 and tint == 0:
            return None
        shifts = {"rm": temp, "gm": tint, "bm": -temp}
        parts = [f"{key}={_fmt(value)}" for key, value in shifts.items() if value != 0]
        return f"colorbalance={':'.join(parts)}"

    def _vibrance_fragment(self) -> str | None:
        if self.config.vibrance == 0:
            return None
        return f"vibrance=intensity={_fmt(self.config.vibrance)}"

    def fragments(self) -> list[str]:
        """Ordered, identity-pruned filter fragments for this grade.

        Order is fixed (``eq -> hue -> colorbalance -> vibrance``) so the same
        config always yields the same graph, which keeps tests and benchmark
        comparisons stable. Any fragment that would be an identity op is omitted.
        """
        candidates = (self._eq_fragment(), self._hue_fragment(),
                      self._balance_fragment(), self._vibrance_fragment())
        return [fragment for fragment in candidates if fragment]

    def is_identity(self) -> bool:
        """True when the grade changes nothing and re-encoding can be skipped."""
        return not self.fragments()

    def chain(self) -> str:
        """The fragments joined into one ``,``-separated filter chain (may be empty)."""
        return ",".join(self.fragments())


def color_chain(config: ColorEffectConfig) -> str:
    """Convenience: the comma-joined color filter chain for ``config``."""
    return ColorBuilder(config).chain()


def apply_color(runner: FFmpegRunner, source: PathLike, output: PathLike, config: ColorEffectConfig, *,
                encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Apply a color grade to ``source``, re-encoding through the runner.

    An identity grade emits no ``-vf`` and simply re-encodes, so the operation is
    still well-defined when nothing changes.
    """
    chain = color_chain(config)
    filter_args = ["-vf", chain] if chain else []
    return execute(runner, ["-i", str(input_path(source)), *filter_args, *encode], output, progress=progress, cancel_event=cancel_event)
