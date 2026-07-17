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
