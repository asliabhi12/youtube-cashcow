from ..context import PipelineContext
from .base import PipelineStep


class DownloadStep(PipelineStep):
    name = "download"
    requires_input = False

    @classmethod
    def validate(cls, options: dict) -> None:
        if not options.get("url"):
            raise ValueError("download requires 'url'")

    def execute(self, context: PipelineContext, runner) -> PipelineContext:
        result = runner.downloader.download_video(str(self.options["url"]))
        if not result.success or not result.file_path:
            raise RuntimeError(result.error or "Downloader returned no media file")
        context.current_file = context.resolve_path(result.file_path)
        context.metadata["download"] = result.model_dump()
        return context
