"""Workflow orchestration tests with downloader and processor kept as collaborators."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import load_config
from src.models import DownloadResult
from src.pipeline import Pipeline, PipelineRunner, PipelineStepError, PipelineValidationError, default_registry
from src.pipeline.models import WorkflowDefinition, WorkflowStep
from src.pipeline.validator import validate_workflow


class FakeDownloader:
    def __init__(self, source): self.source, self.calls = source, []
    def download_video(self, url):
        self.calls.append(url)
        return DownloadResult(success=True, url=url, file_path=str(self.source))


class FakeProcessor:
    def __init__(self): self.calls = []; self.failures = 0; self.resize_options = []
    def _write(self, name, source, output, **options):
        self.calls.append(name); Path(output).write_bytes(Path(source).read_bytes())
    def trim(self, source, output, **options): self._write("trim", source, output, **options)
    def crop(self, source, output, **options): self._write("crop", source, output, **options)
    def resize(self, source, output, *args, **options):
        self.resize_options.append(options); self._write("resize", source, output, **options)
    def thumbnail(self, source, output, timestamp, **options): self._write("thumbnail", source, output, **options)
    def overlay(self, source, image, output, *args, **options):
        self.overlay_calls = getattr(self, "overlay_calls", []); self.overlay_calls.append(("legacy", image, options))
        self._write("overlay", source, output)
    def composite(self, source, output, config, **options):
        self.overlay_calls = getattr(self, "overlay_calls", []); self.overlay_calls.append(("composite", config, options))
        self._write("overlay", source, output)
    def inspect(self, source): return SimpleNamespace(width=100, height=100)


@pytest.fixture
def settings(tmp_path):
    result = load_config("settings.yaml")
    result.pipeline.workspace = str(tmp_path / "workspace")
    result.pipeline.cleanup = True
    return result


def test_parses_and_validates_yaml_workflow(tmp_path):
    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text("name: clip\nsteps:\n  - download:\n      url: https://example.com/video\n  - trim:\n      start: 1\n      end: 2\n  - export:\n      output: final.mp4\n")
    pipeline = Pipeline.from_yaml(workflow_file)
    validate_workflow(pipeline.workflow, default_registry())
    assert [step.name for step in pipeline.workflow.steps] == ["download", "trim", "export"]


def test_validation_reports_order_and_missing_assets(tmp_path):
    workflow = WorkflowDefinition(name="bad", steps=[WorkflowStep(name="trim", options={"start": 0, "end": 1})])
    with pytest.raises(PipelineValidationError, match="first step"):
        validate_workflow(workflow, default_registry())
    missing = WorkflowDefinition(name="bad", steps=[WorkflowStep(name="download", options={"url": "https://example.com"}), WorkflowStep(name="overlay", options={"image": "missing.png"}), WorkflowStep(name="export", options={"output": "final.mp4"})], source_path=tmp_path / "x.yaml")
    with pytest.raises(PipelineValidationError, match="missing file"):
        validate_workflow(missing, default_registry())


def test_execution_order_export_and_cleanup(settings, tmp_path):
    source = tmp_path / "source.mp4"; source.write_bytes(b"video")
    workflow = WorkflowDefinition(name="run", steps=[
        WorkflowStep(name="download", options={"url": "https://example.com/video"}),
        WorkflowStep(name="trim", options={"start": 0, "end": 1}),
        WorkflowStep(name="resize", options={"preset": "shorts"}),
        WorkflowStep(name="thumbnail", options={"second": 0}),
        WorkflowStep(name="export", options={"output": "final.mp4"}),
    ], source_path=tmp_path / "workflow.yaml")
    processor = FakeProcessor()
    events = []
    result = PipelineRunner(settings, default_registry(), downloader=FakeDownloader(source), processor=processor, progress=lambda event, *_: events.append(event)).run(workflow)
    assert processor.calls == ["trim", "resize", "thumbnail"]
    assert processor.resize_options == [{"width": 1080, "height": 1920}]
    assert result.output_file == tmp_path / "final.mp4" and result.output_file.read_bytes() == b"video"
    assert not result.workspace.exists()
    assert events == ["pipeline_started", "step_started", "step_completed", "step_started", "step_completed", "step_started", "step_completed", "step_started", "step_completed", "step_started", "step_completed", "pipeline_completed"]


def test_retry_and_failure_rollback(settings, tmp_path):
    source = tmp_path / "source.mp4"; source.write_bytes(b"video")
    processor = FakeProcessor()
    original = processor.trim
    def flaky(*args, **kwargs):
        processor.failures += 1
        if processor.failures == 1: raise RuntimeError("temporary")
        original(*args, **kwargs)
    processor.trim = flaky
    workflow = WorkflowDefinition(name="retry", steps=[WorkflowStep(name="download", options={"url": "https://example.com"}), WorkflowStep(name="trim", options={"start": 0, "end": 1, "retry": {"attempts": 2}}), WorkflowStep(name="export", options={"output": "retry.mp4"})], source_path=tmp_path / "workflow.yaml")
    result = PipelineRunner(settings, default_registry(), downloader=FakeDownloader(source), processor=processor).run(workflow)
    assert processor.failures == 2 and result.output_file is not None
    failing = WorkflowDefinition(name="fail", steps=[WorkflowStep(name="download", options={"url": "https://example.com"}), WorkflowStep(name="crop", options={"width": 1, "height": 1}), WorkflowStep(name="export", options={"output": "fail.mp4"})], source_path=tmp_path / "workflow.yaml")
    with pytest.raises(PipelineStepError, match="crop"):
        PipelineRunner(settings, default_registry(), downloader=FakeDownloader(source), processor=SimpleNamespace(crop=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("nope")))).run(failing)
    assert not list((tmp_path / "workspace").glob("run_*"))


def test_overlay_step_routes_composite_with_mask(settings, tmp_path):
    source = tmp_path / "source.mp4"; source.write_bytes(b"video")
    overlay_media = tmp_path / "logo.png"; overlay_media.write_bytes(b"image")
    workflow = WorkflowDefinition(name="composite", steps=[
        WorkflowStep(name="source", options={"path": str(source)}),
        WorkflowStep(name="overlay", options={"source": "logo.png", "position": {"x": "center", "y": "center"}, "scale": 0.4, "opacity": 1.0, "mask": {"type": "circle", "feather": 40}}),
        WorkflowStep(name="export", options={"output": "final.mp4"}),
    ], source_path=tmp_path / "workflow.yaml")
    processor = FakeProcessor()
    result = PipelineRunner(settings, default_registry(), processor=processor).run(workflow)
    assert processor.calls == ["overlay"]
    kind, config, _ = processor.overlay_calls[0]
    assert kind == "composite"
    assert config["scale"] == 0.4 and config["x"] == "center" and config["y"] == "center"
    assert config["mask"] == {"type": "circle", "feather": 40}
    assert result.output_file == tmp_path / "final.mp4"


def test_overlay_step_preserves_legacy_image(settings, tmp_path):
    source = tmp_path / "source.mp4"; source.write_bytes(b"video")
    logo = tmp_path / "logo.png"; logo.write_bytes(b"image")
    workflow = WorkflowDefinition(name="legacy", steps=[
        WorkflowStep(name="source", options={"path": str(source)}),
        WorkflowStep(name="overlay", options={"image": "logo.png", "x": 10, "y": 20}),
        WorkflowStep(name="export", options={"output": "final.mp4"}),
    ], source_path=tmp_path / "workflow.yaml")
    processor = FakeProcessor()
    PipelineRunner(settings, default_registry(), processor=processor).run(workflow)
    kind, image, options = processor.overlay_calls[0]
    assert kind == "legacy" and options == {"x": 10, "y": 20}


def test_overlay_validation_requires_a_source(tmp_path):
    bad = WorkflowDefinition(name="bad", steps=[WorkflowStep(name="source", options={"path": "in.mp4"}), WorkflowStep(name="overlay", options={}), WorkflowStep(name="export", options={"output": "o.mp4"})], source_path=tmp_path / "x.yaml")
    with pytest.raises(PipelineValidationError, match="overlay requires"):
        validate_workflow(bad, default_registry())


def test_overlay_validation_reports_missing_source_file(tmp_path):
    source = tmp_path / "in.mp4"; source.write_bytes(b"video")
    missing = WorkflowDefinition(name="missing", steps=[WorkflowStep(name="source", options={"path": str(source)}), WorkflowStep(name="overlay", options={"source": "gone.mp4"}), WorkflowStep(name="export", options={"output": "o.mp4"})], source_path=tmp_path / "x.yaml")
    with pytest.raises(PipelineValidationError, match="missing file"):
        validate_workflow(missing, default_registry())
