from src.processor.planner.operations import OverlayOperation
from .base import PipelineStep


class OverlayStep(PipelineStep):
    """Composite an image or video overlay, optionally masked, onto the video."""

    name = "overlay"

    @classmethod
    def validate(cls, options):
        if not options.get("image") and not options.get("source"):
            raise ValueError("overlay requires 'image' (legacy) or 'source'")
        if options.get("image") and options.get("source"):
            raise ValueError("overlay accepts either 'image' or 'source', not both")

    def execute(self, context, runner):
        if self.options.get("image"):
            image = context.resolve_path(self.options["image"])
            context.assets["overlay"] = image
            options = {key: value for key, value in self.options.items() if key != "image"}
            op = OverlayOperation(
                source=image,
                x=self.options.get("x", 0),
                y=self.options.get("y", 0),
                is_legacy=True,
                legacy_options=options,
            )
        else:
            source = context.resolve_path(self.options["source"])
            context.assets["overlay"] = source
            config = self._build_config(str(source))
            op = OverlayOperation(
                source=source,
                x=config.get("x", "center"),
                y=config.get("y", "center"),
                scale=config.get("scale"),
                width=config.get("width"),
                height=config.get("height"),
                opacity=float(config.get("opacity", 1.0)),
                rotation=float(config.get("rotation", 0)),
                mask=config.get("mask"),
                color=config.get("color"),
                raw_config=config,
            )
        context.render_plan.add(op)
        self._check_step_retry(context, runner)
        return context

    def _build_config(self, source: str) -> dict:
        config = {key: value for key, value in self.options.items() if key not in {"source", "position"}}
        config["source"] = source
        position = self.options.get("position")
        if isinstance(position, dict):
            if "x" in position:
                config["x"] = position["x"]
            if "y" in position:
                config["y"] = position["y"]
        return config
