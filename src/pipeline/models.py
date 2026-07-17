"""Typed workflow definitions and execution records."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RetryConfig(BaseModel):
    attempts: int = Field(default=1, ge=1)


class WorkflowStep(BaseModel):
    name: str
    options: dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinition(BaseModel):
    name: str = Field(min_length=1)
    steps: list[WorkflowStep] = Field(min_length=1)
    retry: RetryConfig | None = None
    source_path: Path | None = Field(default=None, exclude=True)


class StepRecord(BaseModel):
    name: str
    input_file: Path | None = None
    output_file: Path | None = None
    status: str
    attempts: int = 1
    detail: str | None = None


class PipelineResult(BaseModel):
    name: str
    output_file: Path | None = None
    workspace: Path
    history: list[StepRecord]
