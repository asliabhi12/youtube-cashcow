from src.processor.planner.operations import EncodeOperation
from .base import PipelineStep


class EncodeStep(PipelineStep):
    """Specify video encoding profile/quality parameters for the final single pass."""

    name = "encode"

    @classmethod
    def validate(cls, options):
        if options:
            raise ValueError("encode does not accept options; configure encoding defaults in settings.yaml")

    def execute(self, context, runner):
        op = EncodeOperation()
        context.render_plan.add(op)
        return context
