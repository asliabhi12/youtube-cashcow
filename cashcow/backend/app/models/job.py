"""Request and response schemas for the jobs API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Job lifecycle states, mirroring the workflow's progress: a job is "pending"
# until its workflow starts, "running" while the engine executes, then either
# "completed" or "failed" once the pipeline finishes.
JobStatus = Literal["pending", "running", "completed", "failed"]


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
