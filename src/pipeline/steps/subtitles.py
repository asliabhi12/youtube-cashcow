from src.processor.planner.operations import SubtitleOperation
from .base import PipelineStep


class SubtitlesStep(PipelineStep):
    name = "subtitles"

    @classmethod
    def validate(cls, options):
        if not options.get("file"):
            raise ValueError("subtitles requires 'file'")

    def execute(self, context, runner):
        subtitle = context.resolve_path(self.options["file"])
        context.assets["subtitles"] = subtitle
        op = SubtitleOperation(file=subtitle)
        context.render_plan.add(op)
        return context
