"""Pipeline-specific errors, kept separate from media-processing errors."""

from src.exceptions import CashCowError


class PipelineError(CashCowError):
    """Base error for workflow orchestration."""


class PipelineValidationError(PipelineError):
    """Raised when a workflow cannot be safely executed."""


class PipelineExecutionError(PipelineError):
    """Raised when a workflow cannot complete."""


class PipelineStepError(PipelineExecutionError):
    """Raised when a named pipeline step fails."""

    def __init__(self, step: str, message: str) -> None:
        super().__init__(f"Step '{step}' failed: {message}")
        self.step = step


class StepNotFoundError(PipelineValidationError):
    """Raised when a workflow references an unregistered step."""
