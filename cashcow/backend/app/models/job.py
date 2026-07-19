"""Request and response schemas for the jobs API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

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


class TrimRange(BaseModel):
    """A start/end clip range in seconds.

    Both bounds are stored as seconds (the UI's dual-handle slider works in
    seconds internally). ``end`` must be strictly greater than ``start`` so the
    range always describes a non-empty clip.
    """

    start: float = Field(ge=0, description="Clip start offset in seconds.")
    end: float = Field(gt=0, description="Clip end offset in seconds.")

    @model_validator(mode="after")
    def _end_after_start(self) -> "TrimRange":
        if self.end <= self.start:
            raise ValueError("trim end must be greater than start")
        return self


class JobCreate(BaseModel):
    """Request body for POST /jobs.

    Beyond the URL, the body carries a *creative profile* — a trim range, a
    profile id, and an export quality — that the workflow adapter injects into
    the fixed processing pipeline. None of these configure the pipeline's steps
    or order; they only supply parameters the existing steps accept.
    """

    url: str = Field(min_length=1, description="YouTube URL to process.")
    trim: TrimRange | None = Field(
        default=None, description="Optional clip range; the whole video is used when omitted."
    )
    profile_id: str | None = Field(
        default=None, description="Creative profile id (see GET /profiles)."
    )
    # Deprecated alias for ``profile_id``, kept so older clients that still send
    # ``preset`` keep working. ``effective_profile_id`` resolves the two.
    preset: str | None = Field(
        default=None, description="Deprecated: use profile_id. Legacy editing-preset slug."
    )
    export_quality: str = Field(
        default="balanced", description="Export quality slug (see GET /export-qualities)."
    )

    @property
    def effective_profile_id(self) -> str:
        """The profile id to run, preferring ``profile_id`` over the legacy
        ``preset`` alias, and defaulting to ``custom`` (the bare pipeline)."""
        return self.profile_id or self.preset or "custom"


class Job(BaseModel):
    """A processing job as returned by the API."""

    id: str
    url: str
    status: JobStatus
    created_at: datetime
    # The creative profile this job was created with, echoed back for display.
    profile_id: str = "custom"
    export_quality: str = "balanced"
    # Populated from the workflow result once it finishes: the produced file on
    # success, or the failure detail on error. Both stay None while pending or
    # running.
    output_file: str | None = None
    # Human-friendly download filename derived from the video title during
    # processing (sanitized, ``.mp4`` appended). None until the title is known;
    # the on-disk file is always ``{id}.mp4`` regardless.
    output_name: str | None = None
    error: str | None = None
