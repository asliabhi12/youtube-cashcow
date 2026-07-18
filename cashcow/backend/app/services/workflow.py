"""Bridge between the REST job API and the existing workflow engine.

Turns a job's URL into the smallest valid workflow the engine accepts
(``download`` then ``export``) and runs it through the project's existing
``PipelineRunner`` on a background thread, so ``POST /jobs`` can return
immediately. Job status is driven by the engine's own progress callback and
final result. Nothing under ``src/`` is modified; this module only adapts
configuration and reports progress back to the job store.
"""

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

from app.services.job_logs import job_log_hub  # noqa: E402
from app.services.jobs import job_store  # noqa: E402

_SETTINGS_FILE = _PROJECT_ROOT / "settings.yaml"
_OUTPUT_DIRNAME = "output"

# Human-readable log lines for each engine step, keyed by step name. The
# minimal workflow only runs ``download`` then ``export``; unknown steps fall
# back to a generic message built from the step name so new steps still log.
_STEP_STARTED_MESSAGES = {
    "download": "Downloading video",
    "export": "Starting export",
}
_STEP_COMPLETED_MESSAGES = {
    "download": "Download complete",
    "export": "Export complete",
}


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


def _build_workflow(job_id: str, url: str) -> WorkflowDefinition:
    """Compose the minimal valid workflow for a URL: download then export."""
    output_path = _PROJECT_ROOT / _OUTPUT_DIRNAME / f"{job_id}.mp4"
    return WorkflowDefinition(
        name=f"job_{job_id}",
        steps=[
            WorkflowStep(name="download", options={"url": url}),
            WorkflowStep(name="export", options={"output": str(output_path)}),
        ],
    )


def _execute(job_id: str, workflow: WorkflowDefinition) -> None:
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
        elif event == "step_failed" and record is not None:
            detail = record.detail or "unknown error"
            job_log_hub.append(job_id, "ERROR", f"Step '{record.name}' failed: {detail}")

    try:
        runner = PipelineRunner(_settings(), default_registry(), progress=on_progress)
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


def start_workflow(job_id: str, url: str) -> None:
    """Start the engine for a job without blocking the caller.

    Builds the workflow, then hands execution to a daemon thread so the HTTP
    request returns immediately while the pipeline runs in the background.
    """
    # Record the pre-execution lifecycle before handing off to the thread, so
    # the history always opens with these lines regardless of when a client
    # subscribes.
    job_log_hub.append(job_id, "INFO", "Job created")
    job_log_hub.append(job_id, "INFO", "Starting workflow")
    workflow = _build_workflow(job_id, url)
    thread = threading.Thread(
        target=_execute,
        args=(job_id, workflow),
        name=f"workflow-{job_id}",
        daemon=True,
    )
    thread.start()
