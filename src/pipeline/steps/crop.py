from src.processor.planner.operations import CropOperation
from .base import PipelineStep


class CropStep(PipelineStep):
    name = "crop"

    @classmethod
    def validate(cls, options):
        if not options.get("width") or not options.get("height"):
            raise ValueError("crop requires positive 'width' and 'height'")

    def execute(self, context, runner):
        op = CropOperation(
            width=int(self.options["width"]),
            height=int(self.options["height"]),
            x=int(self.options.get("x", 0)),
            y=int(self.options.get("y", 0)),
        )
        context.render_plan.add(op)
        return context
