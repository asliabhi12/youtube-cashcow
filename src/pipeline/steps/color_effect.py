from pydantic import ValidationError

from src.processor.color import color_chain
from src.processor.models import ColorEffectConfig
from src.processor.planner.operations import ColorOperation

from .base import PipelineStep


class ColorEffectStep(PipelineStep):
    """Apply a color grade (brightness/contrast/saturation/gamma/hue/…) to media."""

    name = "color_effect"

    @classmethod
    def validate(cls, options):
        try:
            ColorEffectConfig(**options)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    def execute(self, context, runner):
        config = ColorEffectConfig(**self.options)
        if not color_chain(config):
            return context  # identity grade: nothing to do
        op = ColorOperation(
            brightness=config.brightness,
            contrast=config.contrast,
            saturation=config.saturation,
            gamma=config.gamma,
            hue=config.hue,
        )
        context.render_plan.add(op)
        return context
