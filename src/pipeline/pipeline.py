"""Public workflow construction API."""

from pathlib import Path

from .models import WorkflowDefinition
from .validator import load_workflow


class Pipeline:
    def __init__(self, workflow: WorkflowDefinition) -> None:
        self.workflow = workflow

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Pipeline":
        return cls(load_workflow(path))
