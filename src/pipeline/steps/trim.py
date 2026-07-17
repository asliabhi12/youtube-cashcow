from .base import PipelineStep


class TrimStep(PipelineStep):
    name = "trim"
    @classmethod
    def validate(cls, options):
        if "start" not in options or "end" not in options: raise ValueError("trim requires 'start' and 'end'")
    def execute(self, context, runner):
        output = context.next_output(self.name)
        runner.processor.trim(self.input_file(context), str(output), **self.options)
        context.current_file = output
        return context
