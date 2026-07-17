"""Mutable state deliberately shared between otherwise independent steps."""

from pathlib import Path
from typing import Any

from .models import StepRecord


class PipelineContext:
    """Holds current media, discovered assets, metadata, and step history."""

    def __init__(self, workspace: Path, workflow_directory: Path) -> None:
        self.workspace = workspace
        self.workflow_directory = workflow_directory
        self.current_file: Path | None = None
        self.output_file: Path | None = None
        self.metadata: dict[str, Any] = {}
        self.assets: dict[str, Path] = {}
        self.temporary_files: list[Path] = []
        self.history: list[StepRecord] = []

    def next_output(self, step: str, suffix: str = ".mp4") -> Path:
        path = self.workspace / f"{len(self.history) + 1:02d}_{step}{suffix}"
        self.temporary_files.append(path)
        return path

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (self.workflow_directory / path).resolve()
