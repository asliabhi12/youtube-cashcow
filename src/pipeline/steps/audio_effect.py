from pydantic import ValidationError

from src.processor.audio import effect_chain
from src.processor.models import AudioEffectConfig

from .base import PipelineStep


class AudioEffectStep(PipelineStep):
    """Apply one audio effect or a chain of them to the current media.

    Accepts both workflow shapes (a single inline ``{type: ...}`` effect or an
    explicit ``{effects: [...]}`` chain); :class:`AudioEffectConfig` normalises
    them. When every effect resolves to a no-op (an all-identity chain) the step
    skips FFmpeg entirely and leaves the media untouched, so no wasted encode is
    emitted. All FFmpeg work happens downstream through the Processor.
    """

    name = "audio_effect"

    @classmethod
    def validate(cls, options):
        try:
            AudioEffectConfig(**options)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    def execute(self, context, runner):
        config = AudioEffectConfig(**self.options)
        if not effect_chain(config):
            return context  # identity chain: nothing to do, keep current_file.
        output = context.next_output(self.name)
        runner.processor.apply_audio_effect(self.input_file(context), str(output), config)
        context.current_file = output
        return context
