from src.processor.planner.operations import TrimOperation
from .base import PipelineStep


class TrimStep(PipelineStep):
    name = "trim"

    @classmethod
    def validate(cls, options):
        if "start" not in options or "end" not in options:
            raise ValueError("trim requires 'start' and 'end'")

    def execute(self, context, runner):
        op = TrimOperation(start=float(self.options["start"]), end=float(self.options["end"]))
        context.render_plan.add(op)
        self._check_step_retry(context, runner)
        return context
