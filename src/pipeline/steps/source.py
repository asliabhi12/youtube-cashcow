from ..context import PipelineContext
from .base import PipelineStep


class SourceStep(PipelineStep):
    """Seed a workflow with an already-local media file.

    The counterpart to ``download`` for inputs that are not remote: it
    establishes ``context.current_file`` without any FFmpeg work, so any
    workflow (benchmarks included) can run against a file already on disk.
    """

    name = "source"
    requires_input = False

    @classmethod
    def validate(cls, options: dict) -> None:
        if not options.get("path") and not options.get("file"):
            raise ValueError("source requires 'path' (or 'file')")

    def execute(self, context: PipelineContext, runner) -> PipelineContext:
        location = self.options.get("path") or self.options["file"]
        media = context.resolve_path(location)
        if not media.is_file():
            raise RuntimeError(f"source media does not exist: {media}")
        context.current_file = media
        context.metadata["source"] = str(media)
        return context
