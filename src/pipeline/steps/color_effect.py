from pydantic import ValidationError

from src.processor.color import color_chain
from src.processor.models import ColorEffectConfig

from .base import PipelineStep


class ColorEffectStep(PipelineStep):
    """Apply a color grade (brightness/contrast/saturation/gamma/hue/…) to media.

    Every knob has an identity default, so an all-identity grade resolves to an
    empty filter chain and the step skips FFmpeg entirely rather than emitting a
    pointless re-encode. All FFmpeg work happens downstream through the Processor.
    """

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
            return context  # identity grade: nothing to do, keep current_file.
        output = context.next_output(self.name)
        runner.processor.apply_color_effect(self.input_file(context), str(output), config)
        context.current_file = output
        return context
