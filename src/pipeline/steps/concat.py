from src.processor.planner.operations import ConcatOperation
from .base import PipelineStep


class ConcatStep(PipelineStep):
    name = "concat"

    @classmethod
    def validate(cls, options):
        if not isinstance(options.get("files"), list) or not options["files"]:
            raise ValueError("concat requires a non-empty 'files' list")

    def execute(self, context, runner):
        files = [context.resolve_path(value) for value in self.options["files"]]
        if context.current_file and self.options.get("include_current", False):
            files.insert(0, context.current_file)
        op = ConcatOperation(files=files)
        context.render_plan.add(op)
        return context
