from src.processor.planner.operations import ResizeOperation
from .base import PipelineStep

PLATFORM_DIMENSIONS = {
    "youtube": (1920, 1080),
    "shorts": (1080, 1920),
    "tiktok": (1080, 1920),
    "instagram": (1080, 1920),
}


class ResizeStep(PipelineStep):
    name = "resize"

    @classmethod
    def validate(cls, options):
        if not options.get("preset") and not (options.get("width") and options.get("height")):
            raise ValueError("resize requires 'preset' or both 'width' and 'height'")
        if "zoom" in options and options["zoom"] < 1.0:
            raise ValueError(f"resize zoom must be >= 1.0 (got {options['zoom']})")

    def execute(self, context, runner):
        options = dict(self.options)
        preset = str(options.get("preset", "")).lower()
        if preset in PLATFORM_DIMENSIONS:
            options.pop("preset")
            width, height = PLATFORM_DIMENSIONS[preset]
            options.setdefault("width", width)
            options.setdefault("height", height)
        w = int(options["width"])
        h = int(options["height"])
        zoom = float(options.get("zoom", 1.0))
        context.render_plan.add(ResizeOperation(width=w, height=h, zoom=zoom))
        return context
