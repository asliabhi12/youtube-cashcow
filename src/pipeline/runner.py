"""Workflow coordinator; intentionally contains no FFmpeg command construction."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from src.config import Settings
from src.downloader import Downloader
from src.logger import get_logger
from src.processor import Processor
from src.utils import ensure_directory

from .context import PipelineContext
from .exceptions import PipelineExecutionError, PipelineStepError
from .models import PipelineResult, StepRecord, WorkflowDefinition
from .registry import StepRegistry
from .validator import validate_workflow

ProgressCallback = Callable[[str, PipelineContext, StepRecord | None], None]


class PipelineRunner:
    """Validate and execute workflow steps using the existing component APIs."""

    def __init__(self, settings: Settings, registry: StepRegistry, *, downloader: Downloader | None = None,
                 processor: Processor | None = None, progress: ProgressCallback | None = None) -> None:
        self.settings = settings
        self.registry = registry
        self.downloader = downloader or Downloader(settings)
        self.processor = processor or Processor(settings)
        self.progress = progress
        self.logger = get_logger("youtube_cashcow.pipeline")

    def _notify(self, event: str, context: PipelineContext, record: StepRecord | None = None) -> None:
        self.logger.info("Pipeline event=%s step=%s", event, record.name if record else "-")
        if self.progress: self.progress(event, context, record)

    def _workspace(self) -> Path:
        root = ensure_directory(self.settings.pipeline.workspace)
        run_id = f"run_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}"
        return ensure_directory(root / run_id)

    @staticmethod
    def _attempts(options: dict, default_attempts: int) -> int:
        """Interpret YAML ``attempts`` as total attempts and integer retry as retries."""
        retry = options.get("retry")
        if retry is None:
            return default_attempts
        if isinstance(retry, dict):
            return max(1, int(retry.get("attempts", default_attempts)))
        return max(1, int(retry) + 1)

    def run(self, workflow: WorkflowDefinition) -> PipelineResult:
        validate_workflow(workflow, self.registry)
        workspace = self._workspace()
        source_dir = workflow.source_path.parent if workflow.source_path else Path.cwd()
        context = PipelineContext(workspace, source_dir)
        self._notify("pipeline_started", context)
        try:
            for definition in workflow.steps:
                raw_options = definition.options
                default_attempts = workflow.retry.attempts if workflow.retry else self.settings.pipeline.retries + 1
                attempts = self._attempts(raw_options, default_attempts)
                options = {key: value for key, value in raw_options.items() if key != "retry"}
                record = StepRecord(name=definition.name, input_file=context.current_file, status="running", attempts=attempts)
                self._notify("step_started", context, record)
                for attempt in range(1, attempts + 1):
                    try:
                        self.registry.create(definition.name, options).execute(context, self)
                        record.status = "completed"
                        record.output_file = context.output_file or context.current_file
                        context.history.append(record)
                        self._notify("step_completed", context, record)
                        break
                    except Exception as exc:
                        if attempt == attempts:
                            record.status, record.detail = "failed", str(exc)
                            context.history.append(record)
                            self._notify("step_failed", context, record)
                            raise PipelineStepError(definition.name, str(exc)) from exc
                        self.logger.warning("Retrying step '%s' (%s/%s): %s", definition.name, attempt, attempts, exc)
            if not context.output_file: context.output_file = context.current_file
            result = PipelineResult(name=workflow.name, output_file=context.output_file, workspace=workspace, history=context.history)
            self._notify("pipeline_completed", context)
            if self.settings.pipeline.cleanup: shutil.rmtree(workspace, ignore_errors=True)
            return result
        except PipelineStepError:
            shutil.rmtree(workspace, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(workspace, ignore_errors=True)
            raise PipelineExecutionError(str(exc)) from exc
