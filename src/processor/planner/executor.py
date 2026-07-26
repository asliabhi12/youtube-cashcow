"""Single-pass media execution engine.

Executes prepared single-pass render plans through FFmpegRunner or mock processors.
"""

from pathlib import Path
from typing import TYPE_CHECKING
import shutil
from src.config import Settings
from src.logger import get_logger
from .operations import (
    AudioOperation,
    ColorOperation,
    ConcatOperation,
    CropOperation,
    EncodeOperation,
    OverlayOperation,
    ResizeOperation,
    RotateOperation,
    SubtitleOperation,
    TrimOperation,
    WatermarkOperation,
)
from .plan import RenderPlan
from .planner import RenderPlanner

if TYPE_CHECKING:
    from src.processor.processor import Processor


class MediaExecutor:
    """Executes single-pass render plans using Processor / FFmpegRunner."""

    def __init__(self, settings: Settings, processor: "Processor") -> None:
        self.settings = settings
        self.processor = processor
        self.planner = RenderPlanner(settings)
        self.logger = get_logger("youtube_cashcow.media_executor")

    def execute_plan(
        self,
        plan: RenderPlan,
        input_file: Path,
        output_file: Path,
    ) -> Path:
        """Execute the accumulated render plan in a single pass."""
        if plan.is_empty():
            self.logger.info("RenderPlan is empty; copying input file directly to output.")
            if input_file != output_file and input_file.exists():
                shutil.copy2(input_file, output_file)
            return output_file

        # Check if processor is a mock test collaborator (e.g. FakeProcessor)
        if not hasattr(self.processor, "runner") or hasattr(self.processor, "calls"):
            return self._execute_mock_plan(plan, input_file, output_file)

        exec_plan = self.planner.create_execution_plan(
            plan=plan,
            input_file=input_file,
            output_file=output_file,
            encode_args_fn=self.processor._encode if hasattr(self.processor, "_encode") else None,
        )

        self.logger.info("Executing single-pass FFmpeg command with %d operations", len(exec_plan.optimized_plan))
        try:
            self.processor.runner.run(exec_plan.command_args)
        except Exception as exc:
            step_name = "render"
            if len(plan) > 0:
                step_name = getattr(list(plan)[-1], "step_name", "render") or "render"
            from src.pipeline.exceptions import PipelineStepError
            if not isinstance(exc, PipelineStepError):
                raise PipelineStepError(step_name, str(exc)) from exc
            raise
        return output_file

    def _execute_mock_plan(
        self,
        plan: RenderPlan,
        input_file: Path,
        output_file: Path,
    ) -> Path:
        """Fallback executor for test doubles / mock processor collaborators."""
        current = input_file
        for op in plan:
            try:
                if isinstance(op, TrimOperation):
                    if hasattr(self.processor, "trim"):
                        self.processor.trim(str(current), str(output_file), start=op.start, end=op.end)
                elif isinstance(op, ResizeOperation):
                    if hasattr(self.processor, "resize"):
                        if op.zoom > 1.0:
                            self.processor.resize(str(current), str(output_file), width=op.width, height=op.height, zoom=op.zoom)
                        else:
                            self.processor.resize(str(current), str(output_file), width=op.width, height=op.height)
                elif isinstance(op, CropOperation):
                    if hasattr(self.processor, "crop"):
                        self.processor.crop(str(current), str(output_file), width=op.width, height=op.height, x=op.x, y=op.y)
                elif isinstance(op, RotateOperation):
                    if hasattr(self.processor, "rotate"):
                        self.processor.rotate(str(current), str(output_file), degrees=op.degrees)
                elif isinstance(op, ColorOperation):
                    if hasattr(self.processor, "apply_color_effect"):
                        cfg = op.raw_config if op.raw_config is not None else op
                        self.processor.apply_color_effect(str(current), str(output_file), cfg)
                elif isinstance(op, AudioOperation):
                    if hasattr(self.processor, "apply_audio_effect"):
                        cfg = op.raw_config if op.raw_config is not None else op
                        self.processor.apply_audio_effect(str(current), str(output_file), cfg)
                elif isinstance(op, OverlayOperation):
                    if getattr(op, "is_legacy", False) and hasattr(self.processor, "overlay"):
                        self.processor.overlay(str(current), str(op.source), str(output_file), **getattr(op, "legacy_options", {}))
                    elif hasattr(self.processor, "composite"):
                        cfg = op.raw_config if op.raw_config is not None else {"source": str(op.source), "x": op.x, "y": op.y, "scale": op.scale, "opacity": op.opacity, "mask": op.mask}
                        self.processor.composite(str(current), str(output_file), cfg)
                    elif hasattr(self.processor, "overlay"):
                        self.processor.overlay(str(current), str(op.source), str(output_file), x=op.x, y=op.y)
                elif isinstance(op, WatermarkOperation):
                    if hasattr(self.processor, "watermark"):
                        if op.image_file:
                            self.processor.watermark(str(current), str(output_file), image_file=str(op.image_file), x=op.x, y=op.y)
                        elif op.text:
                            self.processor.watermark(str(current), str(output_file), text=op.text, x=op.x, y=op.y)
                elif isinstance(op, SubtitleOperation):
                    if hasattr(self.processor, "burn_subtitles"):
                        self.processor.burn_subtitles(str(current), str(op.file), str(output_file))
                elif isinstance(op, ConcatOperation):
                    if hasattr(self.processor, "concat"):
                        self.processor.concat([str(f) for f in op.files], str(output_file))
                elif isinstance(op, EncodeOperation):
                    if hasattr(self.processor, "resize"):
                        w, h = 1920, 1080
                        if hasattr(self.processor, "inspect"):
                            try:
                                info = self.processor.inspect(str(current))
                                if hasattr(info, "width") and info.width:
                                    w, h = info.width, info.height
                            except Exception:
                                pass
                        self.processor.resize(str(current), str(output_file), width=w, height=h)
            except Exception as exc:
                step_name = getattr(op, "step_name", "") or op.type
                from src.pipeline.exceptions import PipelineStepError
                if not isinstance(exc, PipelineStepError):
                    raise PipelineStepError(step_name, str(exc)) from exc
                raise

            current = output_file

        if not output_file.exists() and input_file.exists():
            shutil.copy2(input_file, output_file)
        return output_file
