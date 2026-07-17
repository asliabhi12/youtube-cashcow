import shutil

from .base import PipelineStep


class ExportStep(PipelineStep):
    name = "export"
    @classmethod
    def validate(cls, options):
        if not options.get("output"): raise ValueError("export requires 'output'")
    def execute(self, context, runner):
        target = context.resolve_path(self.options["output"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.input_file(context), target)
        context.output_file = target
        return context
