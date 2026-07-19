"""Map engine pipeline events onto a single 0-100 job progress percentage.

The workflow engine reports only *step boundary* events (a step started,
completed, or failed) — it exposes no real-time download or encode percentage.
So overall progress advances to a fixed floor when each stage begins and holds
there until the next stage starts; the monotonic guard in the job store keeps it
from ever moving backwards. This mirrors the product's weighted bands:

    queued              0%
    downloading         0-20%
    analyzing           20-25%
    trimming            25-35%
    creative profile    35-60%
    encoding            60-95%
    finalizing          95-96%
    uploading           96-100%
    completed           100%

Only a percentage and a friendly status string ever leave this module; internal
step names are translated to human-readable messages and never exposed as-is.
"""

from __future__ import annotations

# Progress floor (start of the weighted band) and friendly status message shown
# when each pipeline step *begins*. Progress jumps to the floor as the stage
# starts, then holds until the next stage begins. Creative steps (resize, audio,
# color, overlay) share the 35-60% band; each is optional and only fires when the
# profile supplies it, so their floors are ordered within the band.
_STEP_STARTED: dict[str, tuple[int, str]] = {
    "download": (0, "⬇️ Downloading source video..."),
    "trim": (25, "✂️ Trimming video..."),
    "resize": (35, "🎨 Applying creative profile..."),
    "audio_effect": (45, "🎵 Processing audio..."),
    "color_effect": (50, "🎨 Applying creative profile..."),
    "overlay": (55, "🎨 Applying creative profile..."),
    "encode": (60, "🎬 Encoding video..."),
    "export": (95, "📦 Finalizing output..."),
}

# When a step *completes* we may advance to the top of its band before the next
# step's floor (e.g. download completing moves us into the "analyzing" band).
_STEP_COMPLETED: dict[str, tuple[int, str]] = {
    "download": (22, "🔍 Analyzing video..."),
}

# Friendly failure line per stage, so a failed job reads "❌ Failed while
# encoding video" rather than exposing the raw step name.
_STEP_FAILED_LABEL: dict[str, str] = {
    "download": "downloading the source video",
    "trim": "trimming the video",
    "resize": "applying the creative profile",
    "audio_effect": "processing audio",
    "color_effect": "applying the creative profile",
    "overlay": "applying the creative profile",
    "encode": "encoding the video",
    "export": "finalizing the output",
}

# Terminal / lifecycle states not tied to a specific step.
QUEUED = (0, "⏳ Waiting in queue...")
COMPLETED = (100, "✅ Completed")
UPLOAD_COMPLETE = (100, "✅ Uploaded to YouTube")
UPLOAD_FAILED = (99, "❌ YouTube upload failed")
CANCELLING = (0, "⏹️ Cancelling job...")
CANCELLED = (0, "⏹️ Cancelled")


def queued_status(position: int | None) -> str:
    """Friendly queued message, including the queue position when known."""
    if position is not None and position > 0:
        return f"⏳ Waiting in queue (#{position})"
    return QUEUED[1]


def failed_status(step_name: str | None) -> str:
    """Friendly failure message naming the stage that failed."""
    label = _STEP_FAILED_LABEL.get(step_name or "")
    if label is None:
        return "❌ Failed"
    return f"❌ Failed while {label}"


def for_step_started(step_name: str) -> tuple[int, str] | None:
    """Progress floor and status for a step that just started, or None."""
    return _STEP_STARTED.get(step_name)


def for_step_completed(step_name: str) -> tuple[int, str] | None:
    """Progress and status for a step that just completed, or None."""
    return _STEP_COMPLETED.get(step_name)
