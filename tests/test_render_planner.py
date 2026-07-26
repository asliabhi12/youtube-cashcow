"""Tests for the Single-Pass Render Planner Engine."""

from pathlib import Path
from types import SimpleNamespace
import pytest

from src.config import load_config
from src.processor.planner import (
    AudioOperation,
    ColorOperation,
    CropOperation,
    EncodeOperation,
    FFmpegCommandBuilder,
    FilterGraphBuilder,
    MediaExecutor,
    OverlayOperation,
    RenderOperation,
    RenderPlan,
    RenderPlanner,
    ResizeOperation,
    RotateOperation,
    SubtitleOperation,
    TrimOperation,
    WatermarkOperation,
)
from src.pipeline import PipelineRunner, default_registry
from src.pipeline.models import WorkflowDefinition, WorkflowStep


class FakeDownloader:
    def __init__(self, source):
        self.source = source
    def download_video(self, url):
        return SimpleNamespace(success=True, url=url, file_path=str(self.source))


@pytest.fixture
def settings(tmp_path):
    cfg = load_config("settings.yaml")
    cfg.pipeline.workspace = str(tmp_path / "workspace")
    cfg.pipeline.cleanup = False
    return cfg


def test_render_plan_accumulates_and_optimizes():
    plan = RenderPlan()
    assert plan.is_empty()

    op1 = TrimOperation(start=0.0, end=10.0)
    op2 = ResizeOperation(width=1920, height=1080)
    op3 = ResizeOperation(width=1080, height=1920)  # Subsequent resize should override op2
    op4 = ColorOperation(brightness=0.1)

    plan.add(op1)
    plan.add(op2)
    plan.add(op3)
    plan.add(op4)

    assert len(plan) == 4
    optimized = plan.optimize()

    # Optimized plan should keep only the final resize operation in sequence
    op_types = [op.type for op in optimized]
    assert op_types == ["trim", "resize", "color"]
    res_op = [op for op in optimized if isinstance(op, ResizeOperation)][0]
    assert res_op.width == 1080 and res_op.height == 1920


def test_filter_graph_builder_linear():
    plan = RenderPlan()
    plan.add(TrimOperation(start=1.0, end=5.0))
    plan.add(ResizeOperation(width=1080, height=1920))
    plan.add(ColorOperation(brightness=0.2, contrast=1.1))

    builder = FilterGraphBuilder()
    graph = builder.build(plan, Path("input.mp4"))

    assert graph.filter_complex is None
    assert "trim=start=1.0:end=5.0" in graph.video_filters
    assert "scale=1080:1920:force_original_aspect_ratio=decrease" in graph.video_filters
    assert "eq=brightness=0.2:contrast=1.1" in graph.video_filters
    assert "atrim=start=1.0:end=5.0" in graph.audio_filters


def test_filter_graph_builder_complex_overlay(tmp_path):
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"logo")

    plan = RenderPlan()
    plan.add(TrimOperation(start=0.0, end=10.0))
    plan.add(ResizeOperation(width=1920, height=1080))
    plan.add(OverlayOperation(source=logo, x=20, y=30))

    builder = FilterGraphBuilder()
    graph = builder.build(plan, Path("input.mp4"))

    assert graph.filter_complex is not None
    assert "[0:v]" in graph.filter_complex
    assert "[1:v]" in graph.filter_complex
    assert "overlay=x=20:y=30" in graph.filter_complex
    assert graph.extra_inputs == [logo]


def test_filter_graph_builder_overlay_named_position(tmp_path):
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"logo")

    plan = RenderPlan()
    plan.add(OverlayOperation(source=logo, x="center", y="center"))

    builder = FilterGraphBuilder()
    graph = builder.build(plan, Path("input.mp4"))

    assert graph.filter_complex is not None
    assert "overlay=x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2" in graph.filter_complex


def test_ffmpeg_command_builder(settings, tmp_path):
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"logo")

    plan = RenderPlan()
    plan.add(TrimOperation(start=0.0, end=10.0))
    plan.add(ResizeOperation(width=1920, height=1080))
    plan.add(OverlayOperation(source=logo, x=20, y=30))

    planner = RenderPlanner(settings)
    exec_plan = planner.create_execution_plan(plan, tmp_path / "input.mp4", tmp_path / "output.mp4")

    cmd = exec_plan.command_args
    assert cmd[0] == "-y"
    assert cmd[1] == "-i" and cmd[2] == str(tmp_path / "input.mp4")
    assert cmd[3] == "-i" and cmd[4] == str(logo)
    assert "-filter_complex" in cmd
    assert str(tmp_path / "output.mp4") in cmd


def test_single_pass_pipeline_execution(settings, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"media_content")
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"logo_content")

    workflow = WorkflowDefinition(name="single_pass", steps=[
        WorkflowStep(name="download", options={"url": "https://example.com/video"}),
        WorkflowStep(name="trim", options={"start": 0, "end": 5}),
        WorkflowStep(name="resize", options={"preset": "shorts"}),
        WorkflowStep(name="color_effect", options={"brightness": 0.1}),
        WorkflowStep(name="overlay", options={"source": str(logo), "position": {"x": 10, "y": 10}}),
        WorkflowStep(name="export", options={"output": "final.mp4"}),
    ], source_path=tmp_path / "workflow.yaml")

    executed_commands = []
    class RecordingRunner:
        def run(self, args, **kwargs):
            executed_commands.append(args)
            Path(args[-1]).write_bytes(b"rendered_output")
            return "", "", 0.1

    class RecordingProcessor:
        def __init__(self, settings):
            self.settings = settings
            self.runner = RecordingRunner()
        def _encode(self, profile=None):
            return ["-c:v", "libx264", "-c:a", "aac"]
        def execute_plan(self, plan, input_file, output_file):
            return MediaExecutor(self.settings, self).execute_plan(plan, Path(input_file), Path(output_file))

    processor = RecordingProcessor(settings)
    runner = PipelineRunner(settings, default_registry(), downloader=FakeDownloader(source), processor=processor)
    result = runner.run(workflow)

    # Crucial assertion: FFmpeg was executed EXACTLY ONCE for the entire pipeline!
    assert len(executed_commands) == 1
    single_cmd = executed_commands[0]
    assert "-filter_complex" in single_cmd
    assert result.output_file == tmp_path / "final.mp4"
    assert result.output_file.read_bytes() == b"rendered_output"
