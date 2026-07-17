from .base import PipelineStep


class SubtitlesStep(PipelineStep):
    name = "subtitles"
    @classmethod
    def validate(cls, options):
        if not options.get("file"): raise ValueError("subtitles requires 'file'")
    def execute(self, context, runner):
        subtitle = context.resolve_path(self.options["file"])
        output = context.next_output(self.name)
        options = {key: value for key, value in self.options.items() if key != "file"}
        runner.processor.burn_subtitles(self.input_file(context), str(subtitle), str(output), **options)
        context.assets["subtitles"] = subtitle
        context.current_file = output
        return context
