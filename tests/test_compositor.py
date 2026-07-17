"""Tests for the Phase 6 masking and compositing engine.

Following the processor test style, the FFmpegRunner is mocked so no real
FFmpeg is required: each test asserts on the filter graph and arguments the
compositor builds, proving all execution still flows through the runner.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from src.config import load_config
from src.processor import MaskConfig, OverlayConfig, Processor
from src.processor.compositor import _effects_chain, _overlay_chain, composite
from src.processor.mask import MASK_BUILDERS, mask_filter
from src.processor.overlay import cover_scale2ref, resolve_position, rotate_filter, scale_filter


@pytest.fixture
def media(tmp_path):
    video = tmp_path / "base.mp4"; video.write_bytes(b"video")
    image = tmp_path / "logo.png"; image.write_bytes(b"image")
    clip = tmp_path / "clip.mp4"; clip.write_bytes(b"clip")
    return video, image, clip


@pytest.fixture
def processor(monkeypatch):
    instance = Processor(load_config("settings.yaml"))

    def fake_run(args, **kwargs):
        if "-encoders" in args:
            return " V..... h264_videotoolbox\n V..... libx264", "", .01
        Path(args[-1]).write_bytes(b"composited")
        return "", "", .01

    monkeypatch.setattr(instance.runner, "run", fake_run)
    return instance


def _command(processor, video, config, out):
    return " ".join(processor.composite(str(video), str(out), config).command)


# --- mask generation -------------------------------------------------------

def test_circle_mask_filter():
    filter_value = mask_filter(MaskConfig(type="circle"))
    assert filter_value.startswith("format=rgba,geq=")
    assert "min(W,H)/2" in filter_value  # circle radius from the smaller extent
    assert "lte(" in filter_value  # hard edge when no feather


def test_ellipse_mask_uses_independent_radii():
    filter_value = mask_filter(MaskConfig(type="ellipse", width=300, height=150))
    assert "(150.0)" in filter_value and "(75.0)" in filter_value  # rx and ry differ


def test_feather_produces_soft_edge_ramp():
    hard = mask_filter(MaskConfig(type="circle", feather=0))
    soft = mask_filter(MaskConfig(type="circle", feather=40))
    assert "lte(" in hard and "clip(" in soft  # feather switches to a gradient
    assert "40.0" in soft


def test_invert_flips_alpha():
    assert "255-" in mask_filter(MaskConfig(type="circle", invert=True))


def test_unknown_mask_type_is_rejected():
    with pytest.raises(ValueError, match="Unknown mask type"):
        mask_filter(MaskConfig(type="hexagon"))


def test_mask_registry_is_extensible():
    assert {"circle", "ellipse"} <= set(MASK_BUILDERS)


# --- geometry helpers ------------------------------------------------------

def test_named_and_pixel_positions():
    assert resolve_position("center", "center") == ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2")
    assert resolve_position("top_right", 0) == ("main_w-overlay_w", "0")
    assert resolve_position(10, 20) == ("10", "20")


def test_scale_modes():
    # Fixed-pixel scaling stays single-input; fractional scale lives in cover_scale2ref.
    assert scale_filter(width=200) == "scale=200:-1"
    assert scale_filter(height=120) == "scale=-1:120"
    assert scale_filter() is None


def test_cover_scale2ref_sizes_from_frame_not_overlay():
    # The cover factor must reference the base frame via rw/rh (scale2ref's
    # reference dims); main_w/main_h alone are the overlay itself and would be a
    # no-op. force_original_aspect_ratio is ignored by scale2ref, so the ratio is
    # explicit: max(rw/main_w, rh/main_h) grows the overlay until it covers the frame.
    for value in (1.0, 0.5, 2.0):
        expr = cover_scale2ref(value)
        assert expr.startswith("scale2ref=")
        assert "rw/main_w" in expr and "rh/main_h" in expr  # sized from the base frame
        assert f"main_w*{value}*max(rw/main_w,rh/main_h)" in expr
        assert f"main_h*{value}*max(rw/main_w,rh/main_h)" in expr
    assert "iw" not in cover_scale2ref(1.0)  # not relative to the overlay's own width
    # force_original_aspect_ratio proved unreliable for scale2ref; must not be relied on.
    assert "force_original_aspect_ratio" not in cover_scale2ref(1.0)


def test_cover_scale_rejects_non_positive():
    with pytest.raises(ValueError, match="scale must be positive"):
        cover_scale2ref(0)


def test_rotation_filter_only_when_turned():
    assert rotate_filter(0) is None
    assert rotate_filter(360) is None
    assert "rotate=" in rotate_filter(45)


# --- chain assembly --------------------------------------------------------

def test_overlay_chain_order_scale_mask_rotate_opacity():
    # Fixed-pixel scaling keeps scale first in the single-input chain, then effects.
    config = OverlayConfig(source="logo.png", width=200, rotation=30, opacity=0.75,
                           mask=MaskConfig(type="circle", feather=20))
    chain = _overlay_chain(config)
    order = [chain.index(token) for token in ("scale=", "geq=", "rotate=", "colorchannelmixer=aa=0.75")]
    assert order == sorted(order)


def test_effects_chain_order_mask_rotate_opacity():
    # Effects run after any scaling and always in this order, regardless of scale mode.
    config = OverlayConfig(source="logo.png", rotation=30, opacity=0.75,
                           mask=MaskConfig(type="circle", feather=20))
    chain = _effects_chain(config)
    order = [chain.index(token) for token in ("geq=", "rotate=", "colorchannelmixer=aa=0.75")]
    assert order == sorted(order)


def test_chain_without_mask_still_has_alpha():
    chain = _overlay_chain(OverlayConfig(source="logo.png"))
    assert "format=rgba" in chain and "geq=" not in chain


# --- processor.composite (through the runner) ------------------------------

def test_opacity_applied_in_command(processor, media, tmp_path):
    video, image, _ = media
    command = _command(processor, video, OverlayConfig(source=str(image), opacity=0.5), tmp_path / "o.mp4")
    assert "colorchannelmixer=aa=0.5" in command


def test_fixed_pixel_scaling_applied_in_command(processor, media, tmp_path):
    video, image, _ = media
    command = _command(processor, video, OverlayConfig(source=str(image), width=200), tmp_path / "o.mp4")
    assert "scale=200:-1" in command


def test_fractional_scale_covers_frame_not_overlay(processor, media, tmp_path):
    # scale=1.0 sizes the overlay from the base frame (rw/rh) and grows it to cover
    # the frame, so it fills the output with no borders and never uses the overlay's
    # own dimensions (iw/ih) as the target.
    video, image, _ = media
    command = _command(processor, video, OverlayConfig(source=str(image), scale=1.0), tmp_path / "o.mp4")
    assert "scale2ref=" in command
    assert "rw/main_w" in command and "rh/main_h" in command  # sized from the base frame
    assert "scale=iw" not in command  # never relative to the overlay's own size


def test_half_and_double_scale_reference_frame(processor, media, tmp_path):
    video, image, _ = media
    half = _command(processor, video, OverlayConfig(source=str(image), scale=0.5), tmp_path / "h.mp4")
    double = _command(processor, video, OverlayConfig(source=str(image), scale=2.0), tmp_path / "d.mp4")
    assert "main_w*0.5*max(rw/main_w,rh/main_h)" in half
    assert "main_w*2.0*max(rw/main_w,rh/main_h)" in double


def test_cover_scale_preserves_effects_and_position(processor, media, tmp_path):
    # Masking, rotation, opacity and positioning still apply on top of cover-scaling.
    video, image, _ = media
    config = OverlayConfig(source=str(image), scale=1.0, opacity=0.6, rotation=45,
                           x="top_right", mask=MaskConfig(type="circle", feather=10))
    command = _command(processor, video, config, tmp_path / "o.mp4")
    assert "scale2ref=" in command and "geq=" in command
    assert "rotate=" in command and "colorchannelmixer=aa=0.6" in command
    assert "overlay=main_w-overlay_w:0" in command


def test_positioning_applied_in_command(processor, media, tmp_path):
    video, image, _ = media
    command = _command(processor, video, OverlayConfig(source=str(image), x="top_right"), tmp_path / "o.mp4")
    assert "overlay=main_w-overlay_w:0" in command


def test_image_overlay_uses_two_inputs_without_loop(processor, media, tmp_path):
    # The overlay filter repeats the image's single frame across the base's
    # duration, so no unbounded -loop/-shortest stream is needed.
    video, image, _ = media
    command = _command(processor, video, OverlayConfig(source=str(image)), tmp_path / "o.mp4")
    assert "-loop" not in command and "-shortest" not in command
    assert command.count("-i") == 2


def test_video_overlay_uses_two_inputs(processor, media, tmp_path):
    video, _, clip = media
    command = _command(processor, video, OverlayConfig(source=str(clip)), tmp_path / "o.mp4")
    assert "-loop" not in command and command.count("-i") == 2


def test_composite_accepts_plain_dict(processor, media, tmp_path):
    video, image, _ = media
    result = processor.composite(str(video), str(tmp_path / "o.mp4"),
                                 {"source": str(image), "mask": {"type": "circle", "feather": 40}})
    assert "geq=" in " ".join(result.command) and result.output_file.exists()


def test_composite_rejects_conflicting_scaling(media):
    _, image, _ = media
    with pytest.raises(ValueError, match="either 'scale' or explicit"):
        OverlayConfig(source=str(image), scale=0.5, width=100)


def test_composite_missing_overlay_source_raises(processor, media, tmp_path):
    video, _, _ = media
    with pytest.raises(Exception):
        processor.composite(str(video), str(tmp_path / "o.mp4"), OverlayConfig(source=str(tmp_path / "nope.png")))


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg integration binaries are unavailable")
def test_composite_integration_image_and_video_overlays(tmp_path):
    """Prove the masked/feathered filter graph actually runs under real FFmpeg."""
    base = tmp_path / "base.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=2",
                    "-c:v", "libx264", str(base)], check=True, capture_output=True)
    logo = tmp_path / "logo.png"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=160x160:d=1",
                    "-frames:v", "1", str(logo)], check=True, capture_output=True)
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=green:s=120x120:d=1",
                    "-c:v", "libx264", str(clip)], check=True, capture_output=True)

    processor = Processor(load_config("settings.yaml"))
    image_out = processor.composite(str(base), str(tmp_path / "img.mp4"),
                                    OverlayConfig(source=str(logo), scale=0.4, opacity=0.8,
                                                  mask=MaskConfig(type="circle", feather=20)))
    video_out = processor.composite(str(base), str(tmp_path / "vid.mp4"),
                                    OverlayConfig(source=str(clip), x="top_right",
                                                  mask=MaskConfig(type="ellipse", width=100, height=60)))
    assert image_out.output_file.stat().st_size > 0
    assert video_out.output_file.stat().st_size > 0
    info = processor.inspect(str(image_out.output_file))
    assert info.width == 320 and info.height == 240  # base geometry preserved


def _frame_min_luma(path) -> int:
    """Lowest gray value in the first frame (0 => a black region such as a border)."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        check=True, capture_output=True,
    ).stdout
    return min(raw)


def _make_color(path, color, size):
    frames = ["-frames:v", "1"] if str(path).endswith(".png") else []
    codec = [] if str(path).endswith(".png") else ["-c:v", "libx264"]
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={size}:d=1",
                    *frames, *codec, str(path)], check=True, capture_output=True)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg integration binaries are unavailable")
@pytest.mark.parametrize("base_size, overlay_ext, overlay_size, out_w, out_h", [
    ("270x480", ".png", "400x100", 270, 480),  # landscape image overlay on portrait video
    ("270x480", ".mp4", "400x100", 270, 480),  # landscape video overlay on portrait video
    ("480x270", ".png", "100x400", 480, 270),  # portrait image overlay on landscape video
    ("480x270", ".mp4", "100x400", 480, 270),  # portrait video overlay on landscape video
    # Small overlays are the discriminating case: an unscaled overlay would leave a
    # border, so these fail unless the overlay is genuinely grown to cover the frame.
    ("480x480", ".png", "120x120", 480, 480),  # small square image overlay
    ("480x480", ".mp4", "120x120", 480, 480),  # small square video overlay
    ("270x480", ".png", "160x160", 270, 480),  # small square image overlay on portrait
])
def test_cover_scale_fills_frame_without_borders(tmp_path, base_size, overlay_ext, overlay_size, out_w, out_h):
    """scale=1.0 must fully cover the frame (no black borders) and keep base geometry.

    The base is black and the overlay a solid opaque white sized against the *frame*,
    so any residual black pixel would be an uncovered border. A mismatched aspect
    ratio between overlay and base is the case that used to leave gaps.
    """
    base = tmp_path / "base.mp4"
    _make_color(base, "black", base_size)
    overlay_src = tmp_path / f"ov{overlay_ext}"
    _make_color(overlay_src, "white", overlay_size)

    processor = Processor(load_config("settings.yaml"))
    result = processor.composite(str(base), str(tmp_path / "out.mp4"),
                                 OverlayConfig(source=str(overlay_src), scale=1.0))

    info = processor.inspect(str(result.output_file))
    assert info.width == out_w and info.height == out_h  # geometry preserved
    assert _frame_min_luma(result.output_file) > 16  # fully covered: no black border


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg integration binaries are unavailable")
def test_partial_scale_leaves_base_visible(tmp_path):
    """scale=0.5 covers only part of the frame, so the black base still shows through."""
    base = tmp_path / "base.mp4"
    _make_color(base, "black", "480x480")
    logo = tmp_path / "logo.png"
    _make_color(logo, "white", "500x500")

    processor = Processor(load_config("settings.yaml"))
    result = processor.composite(str(base), str(tmp_path / "out.mp4"),
                                 OverlayConfig(source=str(logo), scale=0.5))
    assert _frame_min_luma(result.output_file) == 0  # base border remains visible
