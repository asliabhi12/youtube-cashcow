from .base import PipelineStep


class EncodeStep(PipelineStep):
    """Re-encode through Processor's resize API without changing dimensions."""
    name = "encode"
    @classmethod
    def validate(cls, options):
        if options: raise ValueError("encode does not accept options; configure encoding defaults in settings.yaml")
    def execute(self, context, runner):
        info = runner.processor.inspect(self.input_file(context))
        if not info.width or not info.height: raise ValueError("encode requires video dimensions")
        output = context.next_output(self.name)
        runner.processor.resize(self.input_file(context), str(output), info.width, info.height)
        context.current_file = output
        return context
