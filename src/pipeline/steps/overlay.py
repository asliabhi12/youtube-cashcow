from .base import PipelineStep


class OverlayStep(PipelineStep):
    name = "overlay"
    @classmethod
    def validate(cls, options):
        if not options.get("image"): raise ValueError("overlay requires 'image'")
    def execute(self, context, runner):
        image = context.resolve_path(self.options["image"])
        output = context.next_output(self.name)
        options = {key: value for key, value in self.options.items() if key != "image"}
        runner.processor.overlay(self.input_file(context), str(image), str(output), **options)
        context.assets["overlay"] = image
        context.current_file = output
        return context
