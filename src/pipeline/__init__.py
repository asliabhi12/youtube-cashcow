"""Reusable workflow pipeline API."""

from .exceptions import PipelineExecutionError, PipelineStepError, PipelineValidationError, StepNotFoundError
from .models import PipelineResult, WorkflowDefinition, WorkflowStep
from .pipeline import Pipeline
from .registry import StepRegistry
from .runner import PipelineRunner
from .steps import BUILTIN_STEPS


def default_registry() -> StepRegistry:
    registry = StepRegistry()
    for step in BUILTIN_STEPS:
        registry.register(step.name, step)
    return registry


__all__ = ["Pipeline", "PipelineRunner", "PipelineResult", "WorkflowDefinition", "WorkflowStep",
           "StepRegistry", "default_registry", "PipelineExecutionError", "PipelineStepError",
           "PipelineValidationError", "StepNotFoundError"]
