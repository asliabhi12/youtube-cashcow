from .base import PipelineStep


class CropStep(PipelineStep):
    name = "crop"
    @classmethod
    def validate(cls, options):
        if not options.get("width") or not options.get("height"): raise ValueError("crop requires positive 'width' and 'height'")
    def execute(self, context, runner):
        output = context.next_output(self.name)
        runner.processor.crop(self.input_file(context), str(output), **self.options)
        context.current_file = output
        return context
