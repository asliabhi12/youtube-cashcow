from .base import PipelineStep


class WatermarkStep(PipelineStep):
    name = "watermark"
    @classmethod
    def validate(cls, options):
        if bool(options.get("text")) == bool(options.get("image")):
            raise ValueError("watermark requires exactly one of 'text' or 'image'")
    def execute(self, context, runner):
        output = context.next_output(self.name)
        options = dict(self.options)
        image = options.pop("image", None)
        if image:
            options["image_file"] = str(context.resolve_path(image))
            context.assets["watermark"] = context.resolve_path(image)
        runner.processor.watermark(self.input_file(context), str(output), **options)
        context.current_file = output
        return context
