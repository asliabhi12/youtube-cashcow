"""Base contract for small, composable workflow steps."""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..context import PipelineContext
    from ..runner import PipelineRunner


class PipelineStep(ABC):
    name = "base"
    requires_input = True

    def __init__(self, options: dict[str, Any]) -> None:
        self.options = options

    @classmethod
    def validate(cls, options: dict[str, Any]) -> None:
        """Validate static options before execution."""

    @abstractmethod
    def execute(self, context: "PipelineContext", runner: "PipelineRunner") -> "PipelineContext":
        """Apply this operation and return the same updated context."""

    def input_file(self, context: "PipelineContext") -> str:
        if context.current_file is None:
            raise ValueError(f"{self.name} requires media from a preceding step")
        return str(context.current_file)

    def _check_step_retry(self, context: "PipelineContext", runner: "PipelineRunner") -> None:
        """Flush render plan if step-level retry is configured so retries apply to this step."""
        if self.options.get("retry") or (runner and hasattr(runner, "_attempts") and runner._attempts(self.options, 1) > 1):
            context.flush_render_plan(runner, step_name=self.name)
