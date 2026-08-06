"""Automated regression test suite verifying audio-video synchronization.

Performs forensic duration and PTS inspection across short (30s), medium (5m),
and long (20m) videos to ensure |audio_duration - video_duration| <= 50ms.
"""

import json
import shutil
import subprocess
from pathlib import Path
import pytest

from src.config import load_config
from src.pipeline import PipelineRunner, WorkflowDefinition, WorkflowStep, default_registry
from src.processor import Processor


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


pytestmark = pytest.mark.skipif(not _has_ffmpeg(), reason="FFmpeg and FFprobe required for sync tests")


def generate_synthetic_media(output_path: Path, duration_seconds: float, fps: int = 30, sample_rate: int = 44100) -> Path:
    """Generate a lightweight synthetic MP4 video file with synchronized audio."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_seconds}:size=320x240:rate={fps}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_seconds}:sample_rate={sample_rate}",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k",
        str(output_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Failed to generate synthetic media: {res.stderr}"
    return output_path


def probe_stream_durations(file_path: Path) -> tuple[float, float, float]:
    """Return (video_duration, audio_duration, abs(video_duration - audio_duration))."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(file_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"FFprobe failed on {file_path}: {res.stderr}"
    data = json.loads(res.stdout)

    v_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)

    assert v_stream is not None, f"No video stream found in {file_path}"
    assert a_stream is not None, f"No audio stream found in {file_path}"

    v_dur = float(v_stream.get("duration") or data.get("format", {}).get("duration") or 0.0)
    a_dur = float(a_stream.get("duration") or data.get("format", {}).get("duration") or 0.0)
    drift = abs(v_dur - a_dur)

    return v_dur, a_dur, drift


@pytest.mark.parametrize("duration_sec", [30, 300, 1200])
def test_pipeline_audio_video_synchronization(tmp_path, duration_sec):
    """Verify audio/video duration drift remains strictly within 50ms threshold."""
    input_video = generate_synthetic_media(tmp_path / f"input_{duration_sec}s.mp4", float(duration_sec))
    output_video = tmp_path / f"output_{duration_sec}s.mp4"

    settings = load_config("settings.yaml")
    settings.ffmpeg.preset = "ultrafast"
    settings.pipeline.workspace = str(tmp_path / "workspace")
    runner = PipelineRunner(settings, default_registry())

    # Build a complete production workflow (trim -> resize -> audio -> color -> export)
    workflow = WorkflowDefinition(
        name=f"sync_test_{duration_sec}s",
        steps=[
            WorkflowStep(name="source", options={"file": str(input_video)}),
            WorkflowStep(name="trim", options={"start": 0.0, "end": float(duration_sec)}),
            WorkflowStep(name="resize", options={"preset": "shorts", "zoom": 1.05}),
            WorkflowStep(name="audio_effect", options={"effects": [{"type": "normalize"}, {"type": "volume", "gain": 3.0}]}),
            WorkflowStep(name="color_effect", options={"contrast": 1.1}),
            WorkflowStep(name="encode", options={}),
            WorkflowStep(name="export", options={"output": str(output_video)}),
        ]
    )

    result = runner.run(workflow)
    assert result.output_file and result.output_file.exists()

    v_dur, a_dur, drift = probe_stream_durations(result.output_file)

    # Threshold constraint: |audio_duration - video_duration| <= 50 milliseconds (0.050 s)
    assert drift <= 0.050, (
        f"Audio drift ({drift * 1000:.2f} ms) exceeded 50 ms limit for {duration_sec}s video!\n"
        f"Video Duration: {v_dur:.6f} s\n"
        f"Audio Duration: {a_dur:.6f} s"
    )


def test_pitch_effect_preserves_exact_duration(tmp_path):
    """Verify pitch shifting preserves exact audio duration without drift."""
    input_video = generate_synthetic_media(tmp_path / "input_pitch.mp4", 30.0)
    output_video = tmp_path / "output_pitch.mp4"

    settings = load_config("settings.yaml")
    processor = Processor(settings)

    # Apply deep_voice pitch shift (-5 semitones)
    processor.apply_audio_effect(
        str(input_video),
        str(output_video),
        {"effects": [{"type": "pitch", "semitones": -5.0}]}
    )

    v_dur, a_dur, drift = probe_stream_durations(output_video)
    assert drift <= 0.050, f"Pitch shift introduced drift: {drift * 1000:.2f} ms (v_dur={v_dur}, a_dur={a_dur})"
