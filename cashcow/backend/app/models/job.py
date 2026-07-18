"""Request and response schemas for the jobs API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Job lifecycle states. Only "pending" exists this phase; more are added
# when processing is wired up.
JobStatus = Literal["pending"]


class JobCreate(BaseModel):
    """Request body for POST /jobs."""

    url: str = Field(min_length=1, description="YouTube URL to process.")


class Job(BaseModel):
    """A processing job as returned by the API."""

    id: str
    url: str
    status: JobStatus
    created_at: datetime
