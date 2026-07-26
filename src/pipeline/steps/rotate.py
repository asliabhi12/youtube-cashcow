from src.processor.planner.operations import RotateOperation
from .base import PipelineStep


class RotateStep(PipelineStep):
    name = "rotate"

    @classmethod
    def validate(cls, options):
        if "degrees" not in options:
            raise ValueError("rotate requires 'degrees'")

    def execute(self, context, runner):
        op = RotateOperation(degrees=float(self.options["degrees"]))
        context.render_plan.add(op)
        return context
