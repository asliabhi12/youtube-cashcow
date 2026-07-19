"""Bridge between the REST job API and the existing workflow engine.

Turns a job's URL into the smallest valid workflow the engine accepts
(``download`` then ``export``) and runs it through the project's existing
``PipelineRunner`` on a background thread, so ``POST /jobs`` can return
immediately. Job status is driven by the engine's own progress callback and
final result. Nothing under ``src/`` is modified; this module only adapts
configuration and reports progress back to the job store.
"""

import re
import sys
import threading
from functools import lru_cache
from pathlib import Path

# The workflow engine lives in ``src/`` at the repository root, above the
# backend package. Put the root on the import path before importing it so the
# FastAPI process (which does not run from the repo root) reuses the engine
# unchanged. Imports below are intentionally after this line.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import Settings, load_config  # noqa: E402
from src.pipeline import (  # noqa: E402
    PipelineRunner,
    WorkflowDefinition,
    WorkflowStep,
    default_registry,
)
from src.pipeline.context import PipelineContext  # noqa: E402
from src.pipeline.models import StepRecord  # noqa: E402

from app.models.job import TrimRange  # noqa: E402
from app.services.job_logs import job_log_hub  # noqa: E402
from app.services.jobs import job_store  # noqa: E402
from app.services.presets import preset_config, quality_overrides  # noqa: E402

_SETTINGS_FILE = _PROJECT_ROOT / "settings.yaml"
_OUTPUT_DIRNAME = "output"
# Overlay assets bundled with the repo. Preset overlay configs reference an asset
# by bare filename; it is resolved against this directory to an absolute path.
_OVERLAY_ASSET_DIR = _PROJECT_ROOT / "assets" / "overlays"

# Human-readable log lines for each engine step, keyed by step name. Unknown
# steps fall back to a generic message built from the step name, so a new step
# still logs sensibly without a map entry.
_STEP_STARTED_MESSAGES = {
    "download": "Downloading video",
    "trim": "Trimming clip",
    "resize": "Resizing video",
    "audio_effect": "Applying audio effects",
    "color_effect": "Applying color grade",
    "overlay": "Compositing overlay",
    "encode": "Encoding video",
    "export": "Starting export",
}
_STEP_COMPLETED_MESSAGES = {
    "download": "Download complete",
    "trim": "Trim complete",
    "resize": "Resize complete",
    "audio_effect": "Audio effects applied",
    "color_effect": "Color grade applied",
    "overlay": "Overlay composited",
    "encode": "Encode complete",
    "export": "Export complete",
}

# Characters not allowed in filenames on common filesystems, plus control chars.
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Cap the derived name so the full path stays well within filesystem limits;
# Unicode graphemes are preserved, only length is bounded.
_MAX_FILENAME_STEM = 180


def _anchor(value: str) -> str:
    """Resolve a configured path against the repo root and ensure it exists.

    Relative engine paths (``logs``, ``downloads``, ``workspace`` …) are
    resolved from the current working directory. The API server does not run
    from the repo root, so each is anchored to it and its directory created.
    Values that are already absolute are left where they point (joining an
    absolute path discards the root), keeping this idempotent.
    """
    resolved = _PROJECT_ROOT / value
    resolved.mkdir(parents=True, exist_ok=True)
    return str(resolved)


@lru_cache(maxsize=1)
def _settings() -> Settings:
    """Load engine settings once, with engine paths anchored to the repo root.

    The engine resolves its filesystem paths relative to the current working
    directory; the API server does not run from the repo root, so every
    path-bearing config value is rewritten to an absolute path (and its
    directory created) before the engine reads it. In particular
    ``logging.log_dir`` holds ``download_archive.txt``, which the downloader
    opens by relative path. This only adjusts configuration values the engine
    reads — the engine itself is untouched.
    """
    settings = load_config(str(_SETTINGS_FILE))
    settings.logging.log_dir = _anchor(settings.logging.log_dir)
    settings.storage.download_dir = _anchor(settings.storage.download_dir)
    settings.storage.temp_dir = _anchor(settings.storage.temp_dir)
    settings.storage.output_dir = _anchor(settings.storage.output_dir)
    settings.storage.assets_dir = _anchor(settings.storage.assets_dir)
    settings.download.output_directory = _anchor(settings.download.output_directory)
    settings.pipeline.workspace = _anchor(settings.pipeline.workspace)
    return settings


def _settings_for_quality(export_quality: str) -> Settings:
    """Return engine settings with encoder bitrates set for an export quality.

    The cached base settings are deep-copied and only the ``ffmpeg`` bitrate
    fields are overridden, so the shared cache stays immutable and every other
    engine path is unchanged. ``Processor._encode`` / ``PerformanceEncoder``
    honour an explicit ``video_bitrate`` on every backend, so this fully controls
    export quality without touching the engine.
    """
    settings = _settings().model_copy(deep=True)
    for key, value in quality_overrides(export_quality).items():
        setattr(settings.ffmpeg, key, value)
    return settings


def _sanitize_filename(title: str | None, fallback: str) -> str:
    """Turn a video title into a safe ``.mp4`` download filename.

    Illegal filesystem characters and control characters are removed, runs of
    whitespace are collapsed, and the stem is length-bounded. Unicode letters are
    preserved. An empty or unusable title falls back to ``fallback`` (the job id),
    so a name is always produced.
    """
    stem = _ILLEGAL_FILENAME_CHARS.sub("", title or "").strip()
    stem = re.sub(r"\s+", " ", stem)
    # Strip characters that are legal mid-name but problematic as edges.
    stem = stem.strip(" .")
    if not stem:
        stem = fallback
    if len(stem) > _MAX_FILENAME_STEM:
        stem = stem[:_MAX_FILENAME_STEM].rstrip(" .")
    return f"{stem}.mp4"


def _build_workflow(
    job_id: str,
    url: str,
    *,
    trim: TrimRange | None,
    preset: str,
) -> WorkflowDefinition:
    """Compose the full fixed pipeline for a job, parameterised by the preset.

    The step *order* is always the same fixed sequence
    (download → trim → resize → audio → color → overlay → encode → export); a
    creative step is emitted only when the chosen preset supplies a config block
    for it. ``download``, ``encode`` and ``export`` are always present, and
    ``trim`` is included whenever a range is given. This never lets the caller
    add, remove, or reorder steps — it only decides which optional creative
    steps carry configuration.
    """
    config = preset_config(preset)
    output_path = _PROJECT_ROOT / _OUTPUT_DIRNAME / f"{job_id}.mp4"

    steps: list[WorkflowStep] = [WorkflowStep(name="download", options={"url": url})]

    if trim is not None:
        steps.append(WorkflowStep(name="trim", options={"start": trim.start, "end": trim.end}))

    if "resize" in config:
        steps.append(WorkflowStep(name="resize", options=config["resize"]))

    if "audio" in config:
        steps.append(WorkflowStep(name="audio_effect", options=config["audio"]))

    if "color" in config:
        steps.append(WorkflowStep(name="color_effect", options=config["color"]))

    if "overlay" in config:
        steps.append(WorkflowStep(name="overlay", options=_overlay_options(config["overlay"])))

    steps.append(WorkflowStep(name="encode", options={}))
    steps.append(WorkflowStep(name="export", options={"output": str(output_path)}))

    return WorkflowDefinition(name=f"job_{job_id}", steps=steps)


def _overlay_options(overlay: dict) -> dict:
    """Resolve a preset overlay config's ``asset`` to an absolute engine path.

    Preset configs reference a bundled overlay by bare filename (``asset``); the
    engine's overlay step and its file-existence validator expect a ``source``
    path. Resolving to an absolute path here means the workflow validator's file
    check passes regardless of the server's working directory.
    """
    options = {key: value for key, value in overlay.items() if key != "asset"}
    options["source"] = str(_OVERLAY_ASSET_DIR / overlay["asset"])
    return options


def _execute(job_id: str, workflow: WorkflowDefinition, settings: Settings) -> None:
    """Run the workflow to completion, mirroring its progress onto the job."""

    def on_progress(event: str, context: PipelineContext, record: StepRecord | None) -> None:
        # Translate the engine's own progress events into high-level, per-job
        # log lines. The engine is untouched; this only reads what it reports.
        if event == "pipeline_started":
            job_store.set_status(job_id, "running")
            job_log_hub.append(job_id, "INFO", "Loading workflow")
        elif event == "step_started" and record is not None:
            message = _STEP_STARTED_MESSAGES.get(record.name, f"Starting {record.name}")
            job_log_hub.append(job_id, "INFO", message)
        elif event == "step_completed" and record is not None:
            message = _STEP_COMPLETED_MESSAGES.get(record.name, f"Finished {record.name}")
            job_log_hub.append(job_id, "INFO", message)
            # Once the download finishes, the engine has recorded the video's
            # title in the context. Derive the title-based download filename now,
            # during processing (the on-disk file stays ``{job_id}.mp4``).
            if record.name == "download":
                title = context.metadata.get("download", {}).get("title")
                output_name = _sanitize_filename(title, job_id)
                job_store.set_output_name(job_id, output_name)
        elif event == "step_failed" and record is not None:
            detail = record.detail or "unknown error"
            job_log_hub.append(job_id, "ERROR", f"Step '{record.name}' failed: {detail}")

    try:
        runner = PipelineRunner(settings, default_registry(), progress=on_progress)
        result = runner.run(workflow)
        output_file = str(result.output_file) if result.output_file else None
        job_store.set_status(job_id, "completed", output_file=output_file)
        job_log_hub.append(job_id, "INFO", "Job completed")
    except Exception as exc:
        # Any engine failure (download, processing, or export) fails the job
        # rather than crashing the background thread.
        job_store.set_status(job_id, "failed", error=str(exc))
        job_log_hub.append(job_id, "ERROR", f"Job failed: {exc}")
    finally:
        # Close the log stream in every case so subscribed SSE clients receive
        # a terminal event and disconnect instead of hanging on the queue.
        job_log_hub.close(job_id)


def start_workflow(
    job_id: str,
    url: str,
    *,
    trim: TrimRange | None = None,
    preset: str = "custom",
    export_quality: str = "balanced",
) -> None:
    """Start the engine for a job without blocking the caller.

    Builds the full pipeline for the job's creative profile (trim range, editing
    preset, export quality), then hands execution to a daemon thread so the HTTP
    request returns immediately while the pipeline runs in the background.
    """
    # Record the pre-execution lifecycle before handing off to the thread, so
    # the history always opens with these lines regardless of when a client
    # subscribes.
    job_log_hub.append(job_id, "INFO", "Job created")
    job_log_hub.append(job_id, "INFO", "Starting workflow")
    workflow = _build_workflow(job_id, url, trim=trim, preset=preset)
    settings = _settings_for_quality(export_quality)
    thread = threading.Thread(
        target=_execute,
        args=(job_id, workflow, settings),
        name=f"workflow-{job_id}",
        daemon=True,
    )
    thread.start()
