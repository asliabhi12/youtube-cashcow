from .base import PipelineStep


class ConcatStep(PipelineStep):
    name = "concat"
    @classmethod
    def validate(cls, options):
        if not isinstance(options.get("files"), list) or not options["files"]: raise ValueError("concat requires a non-empty 'files' list")
    def execute(self, context, runner):
        files = [str(context.resolve_path(value)) for value in self.options["files"]]
        if context.current_file and self.options.get("include_current", False): files.insert(0, str(context.current_file))
        output = context.next_output(self.name)
        options = {key: value for key, value in self.options.items() if key not in {"files", "include_current"}}
        runner.processor.concat(files, str(output), **options)
        context.current_file = output
        return context
