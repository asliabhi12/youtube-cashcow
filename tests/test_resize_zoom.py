"""Tests for the resize processor's optional centred zoom (punch-in).

Unit tests assert on the generated FFmpeg filter graph through a mocked runner
(no real FFmpeg needed); guarded integration tests prove the graph runs and
preserves the output resolution. Style mirrors test_processor.py / test_compositor.py.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from src.config import load_config
from src.processor import Processor
from src.pipeline import PipelineValidationError, default_registry
from src.pipeline.models import WorkflowDefinition, WorkflowStep
from src.pipeline.validator import validate_workflow


@pytest.fixture
def video(tmp_path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"media")
    return source


@pytest.fixture
def processor(monkeypatch):
    instance = Processor(load_config("settings.yaml"))

    def fake_run(args, **kwargs):
        if "-encoders" in args:
            return " V..... h264_videotoolbox\n V..... libx264", "", .01
        Path(args[-1]).write_bytes(b"processed")
        return "", "", .01

    monkeypatch.setattr(instance.runner, "run", fake_run)
    return instance


def _vf(command: list[str]) -> str:
    """Extract the -vf filter graph from a built command."""
    return command[command.index("-vf") + 1]


# --- filter graph generation -----------------------------------------------

def test_zoom_omitted_matches_legacy_graph(processor, video, tmp_path):
    command = processor.resize(str(video), str(tmp_path / "o.mp4"), preset="1080x1920").command
    assert _vf(command) == "scale=1080:1920:force_original_aspect_ratio=decrease"


def test_zoom_one_emits_no_zoom_filters(processor, video, tmp_path):
    command = processor.resize(str(video), str(tmp_path / "o.mp4"), preset="1080x1920", zoom=1.0).command
    graph = _vf(command)
    assert graph == "scale=1080:1920:force_original_aspect_ratio=decrease"
    assert "crop=" not in graph and "iw*" not in graph


def test_zoom_1_1_uses_cover_factor_then_crop(processor, video, tmp_path):
    # Cover factor max(W/iw, H/ih) guarantees the frame covers the target before
    # the user's zoom is applied on top, so crop can never receive a small frame.
    graph = _vf(processor.resize(str(video), str(tmp_path / "o.mp4"), preset="1080x1920", zoom=1.1).command)
    assert graph == (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "scale=iw*max(1080/iw\\,1920/ih)*1.1:ih*max(1080/iw\\,1920/ih)*1.1,"
        "crop=1080:1920"
    )


def test_zoom_1_3_uses_cover_factor_then_crop(processor, video, tmp_path):
    graph = _vf(processor.resize(str(video), str(tmp_path / "o.mp4"), width=1920, height=1080, zoom=1.3).command)
    assert graph == (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "scale=iw*max(1920/iw\\,1080/ih)*1.3:ih*max(1920/iw\\,1080/ih)*1.3,"
        "crop=1920:1080"
    )


def test_padding_and_zoom_reorder_pad_after_crop(processor, video, tmp_path):
    # With zoom, the pipeline is resize -> cover-zoom -> crop -> pad, so zoom acts
    # on the resized image rather than enlarging black padding.
    graph = _vf(processor.resize(str(video), str(tmp_path / "o.mp4"), preset="1080x1920", padding=True, zoom=1.15).command)
    assert graph == (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "scale=iw*max(1080/iw\\,1920/ih)*1.15:ih*max(1080/iw\\,1920/ih)*1.15,"
        "crop=1080:1920,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    )


def test_padding_without_zoom_unchanged(processor, video, tmp_path):
    # Byte-identical to the pre-zoom implementation: pad directly after scale.
    graph = _vf(processor.resize(str(video), str(tmp_path / "o.mp4"), preset="1080x1920", padding=True).command)
    assert graph == "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    assert "crop=" not in graph


def test_preset_and_zoom(processor, video, tmp_path):
    graph = _vf(processor.resize(str(video), str(tmp_path / "o.mp4"), preset="720p", zoom=1.25).command)
    assert graph == (
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "scale=iw*max(1280/iw\\,720/ih)*1.25:ih*max(1280/iw\\,720/ih)*1.25,"
        "crop=1280:720"
    )


def test_crop_dimensions_always_equal_target(processor, video, tmp_path):
    # The crop stage must always request exactly the target dims, never larger
    # (the cover-scale before it guarantees the frame is at least that big).
    graph = _vf(processor.resize(str(video), str(tmp_path / "o.mp4"), preset="1080x1920", zoom=1.3).command)
    crop = [p for p in graph.split(",") if p.startswith("crop=")][0]
    assert crop == "crop=1080:1920"


# --- validation ------------------------------------------------------------

def test_invalid_zoom_below_one_rejected(processor, video, tmp_path):
    with pytest.raises(ValueError, match="zoom must be >= 1.0"):
        processor.resize(str(video), str(tmp_path / "o.mp4"), preset="1080x1920", zoom=0.9)


def test_pipeline_step_validation_rejects_zoom_below_one():
    bad = WorkflowDefinition(name="bad", steps=[
        WorkflowStep(name="source", options={"path": "in.mp4"}),
        WorkflowStep(name="resize", options={"preset": "shorts", "zoom": 0.5}),
        WorkflowStep(name="export", options={"output": "o.mp4"}),
    ], source_path=Path("x.yaml"))
    with pytest.raises(PipelineValidationError, match="zoom must be >= 1.0"):
        validate_workflow(bad, default_registry())


def test_pipeline_step_validation_accepts_zoom_at_or_above_one():
    ok = WorkflowDefinition(name="ok", steps=[
        WorkflowStep(name="source", options={"path": "in.mp4"}),
        WorkflowStep(name="resize", options={"preset": "shorts", "zoom": 1.15}),
        WorkflowStep(name="export", options={"output": "o.mp4"}),
    ], source_path=Path("x.yaml"))
    # Source/export file existence is checked elsewhere; the zoom rule must pass.
    ResizeStep_options = ok.steps[1].options
    from src.pipeline.steps.resize import ResizeStep
    ResizeStep.validate(ResizeStep_options)  # no raise


# --- real FFmpeg integration ------------------------------------------------

# The three aspect classes that previously broke the naive crop: a landscape
# source into a portrait preset was the exact case FFmpeg rejected.
ASPECTS = {"landscape": "1920x1080", "portrait": "1080x1920", "square": "800x800"}


def _make_source(path, size):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:duration=1",
                    "-c:v", "libx264", str(path)], check=True, capture_output=True)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg integration binaries are unavailable")
@pytest.mark.parametrize("aspect", list(ASPECTS))
@pytest.mark.parametrize("zoom", [1.15, 1.30])
def test_all_aspects_into_shorts_cover_to_exact_preset(tmp_path, aspect, zoom):
    """Landscape/portrait/square into a portrait preset must cover it exactly.

    This is the regression guard for the original bug: a landscape source scaled
    with force_original_aspect_ratio=decrease is shorter than the target, so the
    cover factor is what makes the crop valid. With zoom > 1 the output must be
    exactly the preset resolution for every input aspect.
    """
    source = tmp_path / f"{aspect}.mp4"
    _make_source(source, ASPECTS[aspect])
    processor = Processor(load_config("settings.yaml"))
    result = processor.resize(str(source), str(tmp_path / "out.mp4"), preset="1080x1920", zoom=zoom)
    info = processor.inspect(str(result.output_file))
    assert info.width == 1080 and info.height == 1920


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg integration binaries are unavailable")
@pytest.mark.parametrize("aspect", list(ASPECTS))
def test_all_aspects_into_shorts_zoom_one_is_legacy_fit_within(tmp_path, aspect):
    """zoom=1.0 keeps the legacy fit-within behaviour (no crop, no forced size).

    Without padding or zoom the frame fits *inside* the target box exactly as the
    pre-zoom processor did, so a mismatched aspect is not upscaled to the full
    preset. The guarantee here is that it still runs and never exceeds the target.
    """
    source = tmp_path / f"{aspect}.mp4"
    _make_source(source, ASPECTS[aspect])
    processor = Processor(load_config("settings.yaml"))
    result = processor.resize(str(source), str(tmp_path / "out.mp4"), preset="1080x1920", zoom=1.0)
    info = processor.inspect(str(result.output_file))
    assert info.width <= 1080 and info.height <= 1920
    assert info.width == 1080 or info.height == 1920  # touches the box on one axis


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg integration binaries are unavailable")
def test_landscape_into_shorts_with_padding_no_zoom(tmp_path):
    """Landscape + padding (no zoom) letterboxes into the portrait preset."""
    source = tmp_path / "landscape.mp4"
    _make_source(source, ASPECTS["landscape"])
    processor = Processor(load_config("settings.yaml"))
    result = processor.resize(str(source), str(tmp_path / "out.mp4"), preset="1080x1920", padding=True)
    info = processor.inspect(str(result.output_file))
    assert info.width == 1080 and info.height == 1920


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg integration binaries are unavailable")
@pytest.mark.parametrize("aspect", list(ASPECTS))
def test_landscape_portrait_square_with_padding_and_zoom(tmp_path, aspect):
    """Padding + zoom together must run for every aspect and keep the preset size."""
    source = tmp_path / f"{aspect}.mp4"
    _make_source(source, ASPECTS[aspect])
    processor = Processor(load_config("settings.yaml"))
    result = processor.resize(str(source), str(tmp_path / "out.mp4"), preset="1080x1920", padding=True, zoom=1.15)
    info = processor.inspect(str(result.output_file))
    assert info.width == 1080 and info.height == 1920
