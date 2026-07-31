from src.processor.planner.operations import WatermarkOperation
from .base import PipelineStep


class WatermarkStep(PipelineStep):
    name = "watermark"

    @classmethod
    def validate(cls, options):
        if bool(options.get("text")) == bool(options.get("image")):
            raise ValueError("watermark requires exactly one of 'text' or 'image'")

    def execute(self, context, runner):
        options = dict(self.options)
        image = options.pop("image", None)
        image_path = None
        if image:
            image_path = context.resolve_path(image)
            context.assets["watermark"] = image_path
        op = WatermarkOperation(
            image_file=image_path,
            text=options.get("text"),
            x=options.get("x", 10),
            y=options.get("y", 10),
            fontsize=int(options.get("fontsize", 24)),
            fontcolor=str(options.get("fontcolor", "white")),
        )
        context.render_plan.add(op)
        return context
