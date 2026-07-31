from pydantic import ValidationError

from src.processor.audio import effect_chain
from src.processor.models import AudioEffectConfig
from src.processor.planner.operations import AudioOperation

from .base import PipelineStep


class AudioEffectStep(PipelineStep):
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
            return context  # identity chain: nothing to do
        effects_list = [e.model_dump() for e in config.effects] if config.effects else []
        op = AudioOperation(
            effects=effects_list,
            raw_config=config,
        )
        context.render_plan.add(op)
        return context
