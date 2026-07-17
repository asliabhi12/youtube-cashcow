"""Workflow parsing and static validation."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .exceptions import PipelineValidationError
from .models import WorkflowDefinition, WorkflowStep
from .registry import StepRegistry


# Step -> option keys whose values are file paths that must exist before running.
# ``overlay`` carries two mutually exclusive keys (legacy ``image`` and Phase 6
# ``source``); ``LIST_FILE_OPTIONS`` marks keys whose value is a list of paths.
FILE_OPTIONS = {"overlay": ("image", "source"), "subtitles": ("file",), "concat": ("files",), "watermark": ("image",)}
LIST_FILE_OPTIONS = {"files"}


def load_workflow(path: str | Path) -> WorkflowDefinition:
    source = Path(path).expanduser().resolve()
    if not source.is_file(): raise PipelineValidationError(f"Workflow file does not exist: {source}")
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PipelineValidationError(f"Invalid workflow YAML: {exc}") from exc
    if not isinstance(raw, dict): raise PipelineValidationError("Workflow YAML must contain a mapping")
    steps: list[WorkflowStep] = []
    for entry in raw.get("steps", []):
        if not isinstance(entry, dict) or len(entry) != 1:
            raise PipelineValidationError("Each workflow step must be a one-key mapping")
        name, options = next(iter(entry.items()))
        if not isinstance(options, dict): raise PipelineValidationError(f"Step '{name}' options must be a mapping")
        steps.append(WorkflowStep(name=name, options=options))
    try:
        # A missing/empty/null ``name`` is not an error: fall back to the file
        # stem, a stable non-empty identifier. Passing "" here instead would
        # violate WorkflowDefinition's min_length=1 and surface a cryptic error.
        return WorkflowDefinition(name=raw.get("name") or source.stem, steps=steps, retry=raw.get("retry"), source_path=source)
    except ValidationError as exc:
        raise PipelineValidationError(f"Invalid workflow: {exc}") from exc


def validate_workflow(workflow: WorkflowDefinition, registry: StepRegistry) -> None:
    names = [step.name.lower() for step in workflow.steps]
    if names[0] not in {"download", "source", "concat"}:
        raise PipelineValidationError("The first step must establish input media ('download', 'source', or 'concat')")
    if names.count("download") > 1 or names.count("export") > 1:
        raise PipelineValidationError("A workflow may contain at most one download and one export step")
    if "export" not in names or names[-1] != "export":
        raise PipelineValidationError("A workflow must end with exactly one export step")
    for step in workflow.steps:
        if not registry.contains(step.name):
            registry.create(step.name, step.options)  # raises a typed descriptive error
        instance = registry.create(step.name, step.options)
        try:
            instance.validate(step.options)
        except (TypeError, ValueError) as exc:
            raise PipelineValidationError(f"Invalid '{step.name}' configuration: {exc}") from exc
        values: list[Any] = []
        for option in FILE_OPTIONS.get(step.name.lower(), ()):
            raw = step.options.get(option)
            values.extend(raw if option in LIST_FILE_OPTIONS and isinstance(raw, list) else [raw])
        for value in values:
            if value:
                file_path = Path(value)
                if not file_path.is_absolute(): file_path = (workflow.source_path.parent / file_path).resolve() if workflow.source_path else file_path
                if not file_path.is_file():
                    raise PipelineValidationError(f"Step '{step.name}' references missing file: {file_path}")
