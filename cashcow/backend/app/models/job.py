"""Request and response schemas for the jobs API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Job lifecycle states, mirroring the workflow's progress: a job is "pending"
# until its workflow starts, "running" while the engine executes, then either
# "completed" or "failed" once the pipeline finishes.
JobStatus = Literal["pending", "running", "completed", "failed"]

# Severity of a per-job log entry. INFO for normal progress, WARNING for
# recoverable issues (e.g. a retried step), ERROR when the job fails.
JobLogLevel = Literal["INFO", "WARNING", "ERROR"]


class JobLogEntry(BaseModel):
    """A single high-level log line for a job's workflow execution.

    Produced by the adapter (not the engine) as the workflow starts, completes,
    or fails a stage, and streamed to the UI so users can watch progress live.
    """

    timestamp: datetime
    level: JobLogLevel
    message: str


class JobCreate(BaseModel):
    """Request body for POST /jobs."""

    url: str = Field(min_length=1, description="YouTube URL to process.")


class Job(BaseModel):
    """A processing job as returned by the API."""

    id: str
    url: str
    status: JobStatus
    created_at: datetime
    # Populated from the workflow result once it finishes: the produced file on
    # success, or the failure detail on error. Both stay None while pending or
    # running.
    output_file: str | None = None
    error: str | None = None
