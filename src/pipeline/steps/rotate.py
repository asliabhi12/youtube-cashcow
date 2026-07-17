from .base import PipelineStep


class RotateStep(PipelineStep):
    name = "rotate"
    @classmethod
    def validate(cls, options):
        if "degrees" not in options: raise ValueError("rotate requires 'degrees'")
    def execute(self, context, runner):
        output = context.next_output(self.name)
        runner.processor.rotate(self.input_file(context), str(output), **self.options)
        context.current_file = output
        return context
