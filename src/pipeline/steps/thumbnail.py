from .base import PipelineStep


class ThumbnailStep(PipelineStep):
    name = "thumbnail"
    @classmethod
    def validate(cls, options):
        if "second" not in options and "timestamp" not in options: raise ValueError("thumbnail requires 'second' or 'timestamp'")
    def execute(self, context, runner):
        output = context.next_output(self.name, ".jpg")
        options = dict(self.options)
        timestamp = options.pop("second", options.pop("timestamp", 0))
        runner.processor.thumbnail(self.input_file(context), str(output), timestamp, **options)
        context.assets["thumbnail"] = output
        # A thumbnail is a side effect; it must not replace the current video.
        return context
