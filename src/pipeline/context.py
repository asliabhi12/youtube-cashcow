"""Mutable state deliberately shared between otherwise independent steps."""

from pathlib import Path
from typing import Any, TYPE_CHECKING

from src.processor.planner.plan import RenderPlan
from .models import StepRecord

if TYPE_CHECKING:
    from .runner import PipelineRunner


class PipelineContext:
    """Holds current media, discovered assets, metadata, step history, and accumulated render plan."""

    def __init__(self, workspace: Path, workflow_directory: Path) -> None:
        self.workspace = workspace
        self.workflow_directory = workflow_directory
        self.current_file: Path | None = None
        self.output_file: Path | None = None
        self.metadata: dict[str, Any] = {}
        self.assets: dict[str, Path] = {}
        self.temporary_files: list[Path] = []
        self.history: list[StepRecord] = []
        self.render_plan = RenderPlan()

    def next_output(self, step: str, suffix: str = ".mp4") -> Path:
        path = self.workspace / f"{len(self.history) + 1:02d}_{step}{suffix}"
        self.temporary_files.append(path)
        return path

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (self.workflow_directory / path).resolve()

    def flush_render_plan(self, runner: "PipelineRunner", step_name: str = "render") -> Path | None:
        """Execute accumulated render plan in a single pass if operations are pending."""
        if self.render_plan.is_empty() or self.current_file is None:
            return self.current_file

        output = self.next_output(step_name)
        plan_to_execute = self.render_plan
        self.render_plan = RenderPlan()  # Reset render plan so operations don't accumulate on retry
        if hasattr(runner.processor, "execute_plan"):
            runner.processor.execute_plan(plan_to_execute, self.current_file, output)
        else:
            from src.processor.planner.executor import MediaExecutor
            executor = MediaExecutor(runner.settings, runner.processor)
            executor.execute_plan(plan_to_execute, self.current_file, output)

        self.current_file = output
        return self.current_file
