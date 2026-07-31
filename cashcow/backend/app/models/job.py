"""Request and response schemas for the jobs API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.destination import JobDestination, UploadSettings

# Job lifecycle states. A job is "pending" the instant it is created, "queued"
# while it waits its turn in the FIFO queue, "running" while the engine executes
# it, then either "completed" or "failed" once the pipeline finishes. Only one
# job is ever "running" at a time.
JobStatus = Literal[
    "pending",
    "queued",
    "running",
    "cancelling",
    "cancelled",
    "completed",
    "failed",
    "upload_failed",
]
MetadataStatus = Literal["idle", "generating", "available", "unavailable"]
YouTubeUploadStatus = Literal["idle", "uploading", "uploaded", "failed"]

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


class JobProgress(BaseModel):
    """A live overall-progress update streamed to the UI.

    Carries only the single 0-100 percentage for the whole job and a friendly
    status line describing the current operation — never internal pipeline step
    names. Delivered over the same SSE stream as log entries; the ``progress``
    event name distinguishes the two client-side.
    """

    progress: int = Field(ge=0, le=100)
    status: str


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
    destination_ids: list[str] = Field(
        default_factory=list,
        description="Destination ids selected for publishing. Empty means render only.",
    )
    upload_settings: UploadSettings = Field(
        default_factory=UploadSettings,
        description="Default upload settings applied to each selected destination.",
    )
    title_seed: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Starting idea for AI-generated YouTube metadata.",
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
    # When the job actually started running (left the queue), and when it
    # reached a terminal state. Both None until they happen; used by the UI to
    # show a live elapsed timer that excludes time spent waiting in the queue.
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # The creative profile this job was created with, echoed back for display.
    profile_id: str = "custom"
    export_quality: str = "balanced"
    # Optional user-supplied starting idea for AI-generated metadata. Stored on
    # the job so automatic post-processing metadata generation can use it later.
    title_seed: str | None = None
    # Overall job progress as a single 0-100 percentage, and a friendly,
    # human-readable status line describing the current operation (e.g.
    # "🎬 Encoding video..."). Progress only moves forward; on failure it freezes
    # at the last value reached. These are the only progress details exposed —
    # no internal pipeline step names leak through.
    progress: int = 0
    status_message: str = "⏳ Waiting in queue..."
    # Populated from the workflow result once it finishes: the produced file on
    # success, or the failure detail on error. Both stay None while pending or
    # running.
    output_file: str | None = None
    # Human-friendly download filename derived from the video title during
    # processing (sanitized, ``.mp4`` appended). None until the title is known;
    # the on-disk file is always ``{id}.mp4`` regardless.
    output_name: str | None = None
    error: str | None = None
    # 1-based place in the FIFO queue while the job is "queued"; None otherwise.
    # Computed fresh for each response from the live queue, never stored.
    queue_position: int | None = None
    # AI metadata generation status. ``has_metadata`` is retained as a compact
    # boolean for older clients; ``metadata_status`` lets the UI distinguish
    # generating from unavailable without retry loops.
    has_metadata: bool = False
    metadata_status: MetadataStatus = "idle"
    # YouTube upload state for the final workflow stage. Upload failures do not
    # erase the processed output or metadata; they leave the job retryable.
    youtube_upload_status: YouTubeUploadStatus = "idle"
    youtube_video_id: str | None = None
    youtube_video_url: str | None = None
    youtube_uploaded_at: datetime | None = None
    youtube_upload_error: str | None = None
    upload_attempts: int = 0
    cancel_requested: bool = False
    destinations: list[JobDestination] = Field(default_factory=list)
