"""Unit tests for the isolated FFmpeg processing layer."""

import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import MagicMock

import pytest

from src.config import load_config
from src.processor import InvalidMediaError, Processor, UnsupportedCodecError
from src.processor.ffprobe import FFprobe


@pytest.fixture
def files(tmp_path):
    video = tmp_path / "input.mp4"; video.write_bytes(b"media")
    image = tmp_path / "logo.png"; image.write_bytes(b"image")
    subtitle = tmp_path / "captions.srt"; subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi")
    return video, image, subtitle


@pytest.fixture
def processor(monkeypatch):
    instance = Processor(load_config("settings.yaml"))
    def fake_run(args, **kwargs):
        Path(args[-1]).write_bytes(b"processed")
        return "", "", .01
    monkeypatch.setattr(instance.runner, "run", fake_run)
    return instance


def test_trim_uses_accurate_reencode(processor, files, tmp_path):
    result = processor.trim(str(files[0]), str(tmp_path / "clip.mp4"), 1, 4)
    assert result.output_file.exists()
    assert "-ss" in result.command and "-c:v" in result.command


def test_crop_resize_overlay_watermark_and_subtitles(processor, files, tmp_path):
    video, image, subtitle = files
    assert "crop=100:80:2:3" in processor.crop(str(video), str(tmp_path / "crop.mp4"), 100, 80, 2, 3).command
    assert "pad=1080:1920" in " ".join(processor.resize(str(video), str(tmp_path / "resize.mp4"), preset="1080x1920", padding=True).command)
    assert "overlay=5:6" in " ".join(processor.overlay(str(video), str(image), str(tmp_path / "overlay.mp4"), 5, 6).command)
    assert "drawtext" in " ".join(processor.watermark(str(video), str(tmp_path / "watermark.mp4"), text="brand").command)
    assert "subtitles" in " ".join(processor.burn_subtitles(str(video), str(subtitle), str(tmp_path / "sub.mp4")).command)


def test_thumbnail_and_audio(processor, files, tmp_path):
    video = files[0]
    assert processor.thumbnail(str(video), str(tmp_path / "thumb.jpg"), 2).output_file.exists()
    assert processor.mute(str(video), str(tmp_path / "mute.mp4")).output_file.exists()
    assert processor.extract_audio(str(video), str(tmp_path / "audio.m4a")).output_file.exists()


def test_invalid_trim_and_subtitles(processor, files, tmp_path):
    with pytest.raises(InvalidMediaError): processor.trim(str(files[0]), str(tmp_path / "bad.mp4"), 3, 3)
    with pytest.raises(ValueError): processor.burn_subtitles(str(files[0]), str(files[1]), str(tmp_path / "bad.mp4"))


def test_ffprobe_parses_typed_model(monkeypatch, files):
    probe = FFprobe("ffprobe", MagicMock())
    payload = {"format": {"duration": "12.5", "bit_rate": "1000"}, "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30000/1001"}, {"codec_type": "audio", "codec_name": "aac"}]}
    monkeypatch.setattr(probe.runner, "run", lambda args: (json.dumps(payload), "", 0.01))
    info = probe.inspect(files[0])
    assert info.width == 1920 and info.audio_codec == "aac" and info.fps == pytest.approx(29.97003)


def test_concat_rejects_incompatible_stream_copy(processor, files, tmp_path, monkeypatch):
    second = tmp_path / "second.mp4"; second.write_bytes(b"media")
    monkeypatch.setattr(processor.probe, "inspect", lambda value: MagicMock(codec="h264", width=1920 if "input" in str(value) else 1280, height=1080, fps=30, audio_codec="aac"))
    with pytest.raises(UnsupportedCodecError): processor.concat([str(files[0]), str(second)], str(tmp_path / "joined.mp4"))


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg integration binaries are unavailable")
def test_processor_integration_with_small_local_video(tmp_path):
    """Exercise actual FFmpeg trim, resize, thumbnail, and FFprobe wiring."""
    source = tmp_path / "source.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x90:d=2",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2", "-shortest",
        "-c:v", "libx264", "-c:a", "aac", str(source),
    ], check=True, capture_output=True)
    processor = Processor(load_config("settings.yaml"))
    clip = processor.trim(str(source), str(tmp_path / "clip.mp4"), 0, 1)
    resized = processor.resize(str(clip.output_file), str(tmp_path / "vertical.mp4"), preset="1080x1920", padding=True)
    thumb = processor.thumbnail(str(resized.output_file), str(tmp_path / "thumb.jpg"), .5, width=120)
    info = processor.inspect(str(resized.output_file))
    assert thumb.output_file.stat().st_size > 0
    assert info.width == 1080 and info.height == 1920 and info.has_audio
