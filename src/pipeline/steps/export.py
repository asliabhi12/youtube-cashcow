import shutil
from pathlib import Path
from .base import PipelineStep


class ExportStep(PipelineStep):
    name = "export"

    @classmethod
    def validate(cls, options):
        if not options.get("output"):
            raise ValueError("export requires 'output'")

    def execute(self, context, runner):
        target = context.resolve_path(self.options["output"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if not context.render_plan.is_empty():
            context.flush_render_plan(runner, step_name="export", target_output=target)
        else:
            inp = Path(self.input_file(context))
            if inp != target and inp.exists():
                shutil.copy2(inp, target)
        context.output_file = target
        return context
