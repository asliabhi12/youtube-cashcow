from .base import PipelineStep


class OverlayStep(PipelineStep):
    """Composite an image or video overlay, optionally masked, onto the video.

    Two shapes are accepted for backward compatibility. The legacy shape uses an
    ``image`` key and delegates to the simple image overlay. The Phase 6 shape
    uses a ``source`` (image or video) plus optional ``position``, ``scale``,
    ``opacity``, ``rotation`` and ``mask`` and delegates to the masking-aware
    compositor. Path resolution stays here; all FFmpeg work happens downstream.
    """

    name = "overlay"

    @classmethod
    def validate(cls, options):
        if not options.get("image") and not options.get("source"):
            raise ValueError("overlay requires 'image' (legacy) or 'source'")
        if options.get("image") and options.get("source"):
            raise ValueError("overlay accepts either 'image' or 'source', not both")

    def execute(self, context, runner):
        output = context.next_output(self.name)
        if self.options.get("image"):
            self._legacy_overlay(context, runner, output)
        else:
            self._composite(context, runner, output)
        context.current_file = output
        return context

    def _legacy_overlay(self, context, runner, output):
        image = context.resolve_path(self.options["image"])
        options = {key: value for key, value in self.options.items() if key != "image"}
        runner.processor.overlay(self.input_file(context), str(image), str(output), **options)
        context.assets["overlay"] = image

    def _composite(self, context, runner, output):
        source = context.resolve_path(self.options["source"])
        config = self._build_config(str(source))
        runner.processor.composite(self.input_file(context), str(output), config)
        context.assets["overlay"] = source

    def _build_config(self, source: str) -> dict:
        """Translate the workflow YAML shape into OverlayConfig keyword arguments.

        ``position`` is a convenience mapping in YAML; the model keeps ``x``/``y``
        flat, so it is unpacked here at the pipeline boundary.
        """
        config = {key: value for key, value in self.options.items() if key not in {"source", "position"}}
        config["source"] = source
        position = self.options.get("position")
        if isinstance(position, dict):
            if "x" in position: config["x"] = position["x"]
            if "y" in position: config["y"] = position["y"]
        return config
