from .base import PipelineStep


# Platform names are workflow conveniences.  The Processor intentionally keeps
# resize presets dimension-oriented, so this translation belongs at the boundary.
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
        output = context.next_output(self.name)
        options = dict(self.options)
        preset = str(options.get("preset", "")).lower()
        if preset in PLATFORM_DIMENSIONS:
            options.pop("preset")
            width, height = PLATFORM_DIMENSIONS[preset]
            options.setdefault("width", width)
            options.setdefault("height", height)
        runner.processor.resize(self.input_file(context), str(output), **options)
        context.current_file = output
        return context
