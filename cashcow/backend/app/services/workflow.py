"""Bridge between the REST job API and the existing workflow engine.

Turns a job's URL into the smallest valid workflow the engine accepts
(``download`` then ``export``) and runs it through the project's existing
``PipelineRunner`` on a background thread, so ``POST /jobs`` can return
immediately. Job status is driven by the engine's own progress callback and
final result. Nothing under ``src/`` is modified; this module only adapts
configuration and reports progress back to the job store.
"""

import logging
import re
import sys
import threading
from collections.abc import Callable
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

from app.models.job import JobProgress, TrimRange  # noqa: E402
from app.services import assets, job_progress  # noqa: E402
from app.services.hardened_downloader import HardenedDownloader  # noqa: E402
from app.services.job_logs import job_log_hub  # noqa: E402
from app.services.jobs import job_store  # noqa: E402
from app.services.metadata import metadata_service  # noqa: E402
from app.services.presets import quality_overrides  # noqa: E402
from app.services.profiles import resolve_config  # noqa: E402
from app.services.youtube_upload import YouTubeUploadError, youtube_upload_service  # noqa: E402
from app.services.workflow_cancellation import (  # noqa: E402
    CancellableDownloader,
    CancellableProcessor,
    WorkflowCancelledError,
)

logger = logging.getLogger(__name__)
_ENGINE_PIPELINE_RUNNER = PipelineRunner

_SETTINGS_FILE = _PROJECT_ROOT / "settings.yaml"
_OUTPUT_DIRNAME = "output"

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
_CANCEL_EVENTS: dict[str, threading.Event] = {}
_CANCEL_EVENTS_LOCK = threading.Lock()


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
    profile_id: str,
) -> WorkflowDefinition:
    """Compose the full fixed pipeline for a job, parameterised by the profile.

    The step *order* is always the same fixed sequence
    (download → trim → resize → audio → color → overlay → encode → export); a
    creative step is emitted only when the chosen profile supplies a config block
    for it. ``download``, ``encode`` and ``export`` are always present, and
    ``trim`` is included whenever a range is given. This never lets the caller
    add, remove, or reorder steps — it only decides which optional creative
    steps carry configuration.
    """
    config = resolve_config(profile_id)
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
    """Resolve a profile overlay config's ``asset`` to an absolute engine path.

    Profile configs reference an overlay by bare filename (``asset``); the
    engine's overlay step and its file-existence validator expect a ``source``
    path. The assets service resolves the name across the bundled and user
    directories to an absolute path, so the workflow validator's file check
    passes regardless of the server's working directory. A name that no longer
    resolves (e.g. a since-deleted upload) raises, failing the job cleanly
    rather than passing the engine a path that does not exist.
    """
    options = {key: value for key, value in overlay.items() if key != "asset"}
    resolved = assets.resolve_path(overlay["asset"])
    if resolved is None:
        raise FileNotFoundError(f"overlay asset '{overlay['asset']}' not found")
    options["source"] = str(resolved)
    return options


def _emit_progress(job_id: str, progress: int, status_message: str) -> None:
    """Advance a job's overall progress and broadcast it to live SSE clients.

    The store applies the monotonic, clamped-to-100 guard (progress never moves
    backwards), so we broadcast whatever it settled on — not the raw value asked
    for — keeping the streamed bar and the REST snapshot identical.
    """
    job = job_store.set_progress(job_id, progress, status_message)
    if job is not None:
        job_log_hub.publish_progress(
            job_id, JobProgress(progress=job.progress, status=job.status_message)
        )


def request_workflow_cancel(job_id: str) -> None:
    """Signal an in-flight workflow thread to stop cooperatively."""
    with _CANCEL_EVENTS_LOCK:
        event = _CANCEL_EVENTS.get(job_id)
    if event is not None:
        event.set()


def _register_cancel_event(job_id: str, cancel_event: threading.Event) -> None:
    with _CANCEL_EVENTS_LOCK:
        _CANCEL_EVENTS[job_id] = cancel_event


def _unregister_cancel_event(job_id: str) -> None:
    with _CANCEL_EVENTS_LOCK:
        _CANCEL_EVENTS.pop(job_id, None)


def _raise_if_cancelled(job_id: str, cancel_event: threading.Event) -> None:
    if job_store.is_cancel_requested(job_id):
        cancel_event.set()
    if cancel_event.is_set():
        raise WorkflowCancelledError("Job cancellation requested")


def _execute(
    job_id: str,
    workflow: WorkflowDefinition,
    settings: Settings,
    on_complete: Callable[[str], None] | None = None,
) -> None:
    """Run the workflow to completion, mirroring its progress onto the job.

    ``on_complete`` (if given) is called with the job id once the job reaches a
    terminal state, after logs are closed. The queue uses it to start the next
    job; it runs on this job's background thread and its failures are swallowed
    so a callback error can never crash the worker or wedge the queue.
    """
    # Track the step in flight so a failure can name the stage in the status
    # line without exposing the internal step name (closed over by on_progress).
    last_step: dict[str, str | None] = {"name": None}
    cancel_event = threading.Event()
    _register_cancel_event(job_id, cancel_event)

    def on_progress(event: str, context: PipelineContext, record: StepRecord | None) -> None:
        _raise_if_cancelled(job_id, cancel_event)
        # Translate the engine's own progress events into high-level, per-job
        # log lines and a single overall progress bar. The engine is untouched;
        # this only reads what it reports.
        if event == "pipeline_started":
            job_store.set_status(job_id, "running")
            job_log_hub.append(job_id, "INFO", "Loading workflow")
        elif event == "step_started" and record is not None:
            last_step["name"] = record.name
            message = _STEP_STARTED_MESSAGES.get(record.name, f"Starting {record.name}")
            job_log_hub.append(job_id, "INFO", message)
            mapped = job_progress.for_step_started(record.name)
            if mapped is not None:
                _emit_progress(job_id, mapped[0], mapped[1])
        elif event == "step_completed" and record is not None:
            message = _STEP_COMPLETED_MESSAGES.get(record.name, f"Finished {record.name}")
            job_log_hub.append(job_id, "INFO", message)
            mapped = job_progress.for_step_completed(record.name)
            if mapped is not None:
                _emit_progress(job_id, mapped[0], mapped[1])
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
            # Freeze progress at its current value and show which stage failed.
            _emit_progress(job_id, 0, job_progress.failed_status(record.name))

    try:
        _raise_if_cancelled(job_id, cancel_event)
        # Inject the hardened downloader so YouTube anti-bot options (browser
        # cookies + remote challenge solver) apply to every job. The engine and
        # its default downloader are untouched; this only swaps which downloader
        # the runner uses.
        runner = _build_runner(settings, cancel_event, on_progress)
        result = runner.run(workflow)
        output_file = str(result.output_file) if result.output_file else None
        job_store.set_status(job_id, "running", output_file=output_file)
        _raise_if_cancelled(job_id, cancel_event)
        try:
            metadata_service.generate(
                job_id,
                log=lambda level, message: job_log_hub.append(job_id, level, message),
                fallback=True,
            )
        except Exception as exc:  # noqa: BLE001 - metadata must never fail the job
            logger.error("Workflow error: Metadata generation failed for job %s: %s", job_id, exc)
            job_log_hub.append(job_id, "ERROR", f"Workflow error: {exc}")

        if metadata_service.get(job_id) is None:
            job_log_hub.append(job_id, "INFO", "Workflow transition: FALLBACK_METADATA")
            try:
                context = metadata_service._build_generation_context(job_id, None)
                fallback_metadata = metadata_service._generate_fallback_metadata(
                    job_id, context, lambda lvl, msg: job_log_hub.append(job_id, lvl, msg)
                )
                with metadata_service._lock:
                    metadata_service._metadata[job_id] = fallback_metadata
                job_store.set_metadata_status(job_id, "available")
                job_log_hub.append(job_id, "INFO", "Fallback metadata generated and saved successfully.")
            except Exception as fallback_exc:
                logger.error("Double failure: Could not generate fallback metadata: %s", fallback_exc)
                job_log_hub.append(job_id, "ERROR", f"Workflow error: Could not generate fallback metadata: {fallback_exc}")
        _raise_if_cancelled(job_id, cancel_event)
        
        # State transition to UPLOADING
        job_store.set_progress(job_id, 96, "UPLOADING")
        job_log_hub.append(job_id, "INFO", "Workflow transition: UPLOADING")
        try:
            youtube_upload_service.upload_job(
                job_id,
                progress=lambda progress, message: _upload_progress(
                    job_id, cancel_event, progress, message
                ),
                log=lambda level, message: job_log_hub.append(job_id, level, message),
            )
        except YouTubeUploadError as exc:
            job_store.set_status(job_id, "upload_failed")
            _emit_progress(job_id, *job_progress.UPLOAD_FAILED)
            job_log_hub.append(job_id, "WARNING", "Job output is ready; YouTube upload failed.")
            logger.warning("Workflow upload stage failed for job %s: %s", job_id, exc)
        else:
            # set_status pins progress to 100 on success; broadcast that final bar.
            job_store.set_status(job_id, "completed", output_file=output_file)
            _emit_progress(job_id, *job_progress.UPLOAD_COMPLETE)
            job_log_hub.append(job_id, "INFO", "Job completed")
    except WorkflowCancelledError:
        cancel_event.set()
        job_store.set_status(job_id, "cancelled")
        _emit_progress(job_id, *job_progress.CANCELLED)
        job_log_hub.append(job_id, "WARNING", "Job cancelled")
    except Exception as exc:
        # Any engine failure (download, processing, or export) fails the job
        # rather than crashing the background thread.
        job_store.set_status(job_id, "failed", error=str(exc))
        # Freeze progress where it stopped and name the stage that failed. Passing
        # 0 relies on the store's monotonic guard to leave the bar untouched.
        _emit_progress(job_id, 0, job_progress.failed_status(last_step["name"]))
        job_log_hub.append(job_id, "ERROR", f"Job failed: {exc}")
    finally:
        # Close the log stream in every case so subscribed SSE clients receive
        # a terminal event and disconnect instead of hanging on the queue.
        job_log_hub.close(job_id)
        # Signal completion last, so the next queued job only starts once this
        # one is fully terminal. A callback failure must not crash the worker.
        if on_complete is not None:
            try:
                on_complete(job_id)
            except Exception:  # noqa: BLE001 - completion hook is best-effort
                logger.exception("on_complete hook failed for job %s", job_id)
        _unregister_cancel_event(job_id)


def _upload_progress(
    job_id: str,
    cancel_event: threading.Event,
    progress: int,
    message: str,
) -> None:
    _raise_if_cancelled(job_id, cancel_event)
    _emit_progress(job_id, progress, message)
    _raise_if_cancelled(job_id, cancel_event)


def _build_runner(
    settings: Settings,
    cancel_event: threading.Event,
    on_progress: Callable[[str, PipelineContext, StepRecord | None], None],
):
    """Construct the engine runner, keeping older test doubles compatible."""
    if PipelineRunner is not _ENGINE_PIPELINE_RUNNER:
        return PipelineRunner(
            settings,
            default_registry(),
            downloader=object(),
            progress=on_progress,
        )
    kwargs = {
        "downloader": CancellableDownloader(settings, cancel_event),
        "processor": CancellableProcessor(settings, cancel_event),
        "progress": on_progress,
    }
    try:
        return PipelineRunner(settings, default_registry(), **kwargs)
    except TypeError as exc:
        if "processor" not in str(exc):
            raise
        kwargs.pop("processor")
        return PipelineRunner(settings, default_registry(), **kwargs)


def start_workflow(
    job_id: str,
    url: str,
    *,
    trim: TrimRange | None = None,
    profile_id: str = "custom",
    export_quality: str = "balanced",
    on_complete: Callable[[str], None] | None = None,
) -> None:
    """Start the engine for a job without blocking the caller.

    Builds the full pipeline for the job's creative profile (trim range, creative
    profile, export quality), then hands execution to a daemon thread so the HTTP
    request returns immediately while the pipeline runs in the background.

    ``on_complete`` is invoked with the job id once the job reaches a terminal
    state (from the background thread). The queue passes this to start the next
    job; the workflow itself neither knows nor cares that a queue exists.

    Building the workflow happens synchronously (before the thread starts), so a
    build error — e.g. an overlay asset that no longer resolves — propagates to
    the caller instead of being buried in the background thread. The queue relies
    on this to fail such a job and move on.
    """
    # Record the pre-execution lifecycle before handing off to the thread, so
    # the history always opens with these lines regardless of when a client
    # subscribes.
    job_log_hub.append(job_id, "INFO", "Job created")
    job_log_hub.append(job_id, "INFO", "Starting workflow")
    workflow = _build_workflow(job_id, url, trim=trim, profile_id=profile_id)
    settings = _settings_for_quality(export_quality)
    thread = threading.Thread(
        target=_execute,
        args=(job_id, workflow, settings, on_complete),
        name=f"workflow-{job_id}",
        daemon=True,
    )
    thread.start()
