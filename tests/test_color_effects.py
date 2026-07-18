"""Tests for the Phase 7 color-grading engine and overlay color grading.

Unit tests assert the filter fragments ColorBuilder produces; integration tests
run through the mocked runner; a guarded test proves the grade runs under real
FFmpeg. Overlay color grading is verified through the compositor filter graph.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from src.config import load_config
from src.processor import ColorEffectConfig, MaskConfig, OverlayConfig, Processor
from src.processor.color import ColorBuilder, apply_color, color_chain
from src.processor.compositor import _effects_chain


@pytest.fixture
def media(tmp_path):
    video = tmp_path / "base.mp4"
    video.write_bytes(b"video")
    image = tmp_path / "logo.png"
    image.write_bytes(b"image")
    return video, image


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


# --- fragment generation ---------------------------------------------------

def test_eq_knobs_group_into_one_node():
    chain = color_chain(ColorEffectConfig(brightness=0.05, contrast=1.2, saturation=1.3, gamma=1.1))
    assert chain == "eq=brightness=0.05:contrast=1.2:saturation=1.3:gamma=1.1"


def test_hue_temperature_tint_vibrance_fragments():
    chain = color_chain(ColorEffectConfig(hue=20, temperature=0.3, tint=-0.2, vibrance=0.5))
    assert "hue=h=20" in chain
    assert "colorbalance=rm=0.3:gm=-0.2:bm=-0.3" in chain  # warm axis lifts red, drops blue
    assert "vibrance=intensity=0.5" in chain


def test_fragment_order_is_stable():
    builder = ColorBuilder(ColorEffectConfig(brightness=0.1, hue=10, temperature=0.2, vibrance=0.3))
    fragments = builder.fragments()
    assert fragments == sorted(fragments, key=lambda f: ["eq", "hue", "colorbalance", "vibrance"].index(f.split("=")[0]))


# --- identity elimination --------------------------------------------------

def test_identity_grade_is_empty():
    assert color_chain(ColorEffectConfig()) == ""
    assert ColorBuilder(ColorEffectConfig()).is_identity()


def test_partial_identity_only_emits_changed_knobs():
    # Only saturation changes; brightness/contrast/gamma stay at identity.
    assert color_chain(ColorEffectConfig(saturation=1.5)) == "eq=saturation=1.5"


# --- validation ------------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    {"brightness": 2.0}, {"contrast": 5.0}, {"saturation": -1.0},
    {"gamma": 0}, {"hue": 400}, {"temperature": 2.0}, {"tint": -3.0}, {"vibrance": 5.0},
])
def test_out_of_range_values_rejected(kwargs):
    with pytest.raises(ValueError):
        ColorEffectConfig(**kwargs)


# --- execution through the runner ------------------------------------------

def test_apply_color_effect_puts_chain_in_command(processor, media, tmp_path):
    video, _ = media
    result = processor.apply_color_effect(str(video), str(tmp_path / "o.mp4"),
                                          {"brightness": 0.05, "contrast": 1.2, "saturation": 1.3})
    command = " ".join(result.command)
    assert "-vf" in result.command
    assert "eq=brightness=0.05:contrast=1.2:saturation=1.3" in command


def test_identity_grade_reencodes_without_vf(processor, media, tmp_path):
    video, _ = media
    result = apply_color(processor.runner, str(video), str(tmp_path / "o.mp4"),
                         ColorEffectConfig(), encode=processor._encode())
    assert "-vf" not in result.command
    assert result.output_file.exists()


# --- overlay (selective) color grading -------------------------------------

def test_overlay_color_grade_applied_before_mask_and_opacity():
    # Color must precede mask/rotate/opacity so only the overlay pixels are graded.
    config = OverlayConfig(source="logo.png", opacity=0.8, rotation=15,
                           color=ColorEffectConfig(saturation=1.4, hue=20),
                           mask=MaskConfig(type="circle", feather=10))
    chain = _effects_chain(config)
    order = [chain.index(token) for token in ("eq=", "hue=", "geq=", "rotate=", "colorchannelmixer=aa=0.8")]
    assert order == sorted(order)


def test_overlay_without_color_has_no_grade():
    chain = _effects_chain(OverlayConfig(source="logo.png"))
    assert "eq=" not in chain and "hue=" not in chain


def test_overlay_identity_color_emits_no_grade():
    chain = _effects_chain(OverlayConfig(source="logo.png", color=ColorEffectConfig()))
    assert "eq=" not in chain and "colorbalance=" not in chain


def test_overlay_color_in_composite_command(processor, media, tmp_path):
    video, image = media
    config = OverlayConfig(source=str(image), scale=0.5,
                           color=ColorEffectConfig(brightness=0.1, saturation=1.4, hue=20))
    command = " ".join(processor.composite(str(video), str(tmp_path / "o.mp4"), config).command)
    assert "eq=brightness=0.1:saturation=1.4" in command and "hue=h=20" in command


# --- real FFmpeg integration ------------------------------------------------

@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg integration binaries are unavailable")
@pytest.mark.parametrize("options", [
    {"brightness": 0.1, "contrast": 1.2, "saturation": 1.3},
    {"gamma": 1.4},
    {"hue": 45},
    {"temperature": 0.3, "tint": -0.2},
    {"vibrance": 0.6},
])
def test_color_grade_runs_under_real_ffmpeg(tmp_path, options):
    source = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=160x120:duration=1",
         "-c:v", "libx264", str(source)], check=True, capture_output=True,
    )
    processor = Processor(load_config("settings.yaml"))
    result = processor.apply_color_effect(str(source), str(tmp_path / "out.mp4"), options)
    assert result.output_file.stat().st_size > 0
    info = processor.inspect(str(result.output_file))
    assert info.width == 160 and info.height == 120


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg integration binaries are unavailable")
def test_overlay_color_grading_runs_under_real_ffmpeg(tmp_path):
    """Grading only the overlay must still produce a valid composite."""
    base = tmp_path / "base.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
                    "-c:v", "libx264", str(base)], check=True, capture_output=True)
    logo = tmp_path / "logo.png"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=120x120:d=1",
                    "-frames:v", "1", str(logo)], check=True, capture_output=True)
    processor = Processor(load_config("settings.yaml"))
    result = processor.composite(str(base), str(tmp_path / "out.mp4"),
                                 OverlayConfig(source=str(logo), scale=0.4,
                                               color=ColorEffectConfig(saturation=1.5, hue=30),
                                               mask=MaskConfig(type="circle", feather=10)))
    assert result.output_file.stat().st_size > 0
    info = processor.inspect(str(result.output_file))
    assert info.width == 320 and info.height == 240
