"""Tests for the Phase 7 audio-effects engine.

Following the processor test style, FFmpegRunner is mocked so no real FFmpeg is
needed for the unit/integration tests: each asserts on the ``-af`` filter chain
the builders produce and that execution flows through the runner. A guarded
integration test proves the chains actually run under real FFmpeg.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from src.config import load_config
from src.processor import AudioEffectConfig, Processor
from src.processor.audio import (
    AUDIO_BUILDERS,
    _atempo_chain,
    apply_effects,
    effect_chain,
    effect_fragment,
)
from src.processor.models import AudioEffect


@pytest.fixture
def media(tmp_path):
    video = tmp_path / "base.mp4"
    video.write_bytes(b"video")
    return video


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


# --- individual effect fragments -------------------------------------------

def test_registry_covers_every_documented_effect():
    assert set(AUDIO_BUILDERS) == {
        "pitch", "deep_voice", "chipmunk", "volume", "echo", "bass", "treble", "normalize", "speed",
    }


def test_pitch_shifts_rate_and_compensates_tempo():
    fragment = effect_fragment(AudioEffect(type="pitch", semitones=12))
    # +12 semitones doubles the rate; the atempo chain halves tempo back to 1.0x length.
    assert fragment.startswith("asetrate=88200")
    assert "aresample=44100" in fragment and "atempo=" in fragment


def test_deep_voice_and_chipmunk_use_preset_pitches():
    deep = effect_fragment(AudioEffect(type="deep_voice"))
    chip = effect_fragment(AudioEffect(type="chipmunk"))
    assert deep.startswith("asetrate=") and chip.startswith("asetrate=")
    # Deep lowers the rate below base; chipmunk raises it above base.
    assert int(deep.split("=")[1].split(",")[0]) < 44100
    assert int(chip.split("=")[1].split(",")[0]) > 44100


def test_volume_uses_db_and_bass_treble_default_gain():
    assert effect_fragment(AudioEffect(type="volume", gain=3)) == "volume=3dB"
    assert effect_fragment(AudioEffect(type="bass")) == "bass=g=5"
    assert effect_fragment(AudioEffect(type="treble", gain=8)) == "treble=g=8"


def test_echo_and_normalize_fragments():
    assert effect_fragment(AudioEffect(type="echo")).startswith("aecho=")
    assert effect_fragment(AudioEffect(type="normalize")) == "loudnorm"


def test_speed_decomposes_into_in_range_atempo_stages():
    # 3.0x cannot be a single atempo (max 2.0); it becomes 2.0 * 1.5.
    assert _atempo_chain(3.0) == "atempo=2,atempo=1.5"
    # 0.25x cannot be a single atempo (min 0.5); it becomes 0.5 * 0.5.
    assert _atempo_chain(0.25) == "atempo=0.5,atempo=0.5"
    assert _atempo_chain(1.5) == "atempo=1.5"


def test_atempo_chain_rejects_non_positive_factor():
    with pytest.raises(ValueError, match="tempo factor must be positive"):
        _atempo_chain(0)


# --- identity elimination --------------------------------------------------

def test_identity_effects_emit_nothing():
    assert effect_fragment(AudioEffect(type="volume", gain=0)) is None
    assert effect_fragment(AudioEffect(type="speed", factor=1)) is None
    assert effect_fragment(AudioEffect(type="pitch", semitones=0)) is None


def test_all_identity_chain_is_empty():
    config = AudioEffectConfig(effects=[
        AudioEffect(type="volume", gain=0), AudioEffect(type="speed", factor=1),
    ])
    assert effect_chain(config) == ""


# --- chaining and config shapes --------------------------------------------

def test_single_inline_effect_shape_is_normalized():
    config = AudioEffectConfig(**{"type": "normalize"})
    assert len(config.effects) == 1 and config.effects[0].type == "normalize"
    assert effect_chain(config) == "loudnorm"


def test_explicit_chain_applies_in_order():
    config = AudioEffectConfig(**{"effects": [
        {"type": "normalize"}, {"type": "bass"}, {"type": "volume", "gain": 4},
    ]})
    assert effect_chain(config) == "loudnorm,bass=g=5,volume=4dB"


def test_unknown_effect_is_rejected():
    with pytest.raises(ValueError, match="Unknown audio effect"):
        effect_fragment(AudioEffect(type="reverb"))


# --- validation ------------------------------------------------------------

def test_volume_gain_out_of_range_rejected():
    with pytest.raises(ValueError, match="gain must be between"):
        AudioEffect(type="volume", gain=200)


def test_pitch_semitones_out_of_range_rejected():
    with pytest.raises(ValueError, match="semitones must be between"):
        AudioEffect(type="pitch", semitones=48)


def test_speed_factor_out_of_range_rejected():
    with pytest.raises(ValueError, match="factor must be between"):
        AudioEffect(type="speed", factor=0.1)


def test_speed_factor_must_be_positive():
    with pytest.raises(ValueError):
        AudioEffect(type="speed", factor=0)


# --- execution through the runner ------------------------------------------

def test_apply_audio_effect_puts_chain_in_command(processor, media, tmp_path):
    result = processor.apply_audio_effect(str(media), str(tmp_path / "o.mp4"),
                                          {"effects": [{"type": "bass"}, {"type": "volume", "gain": 6}]})
    command = " ".join(result.command)
    assert "-af" in result.command
    assert "bass=g=5,volume=6dB" in command
    assert result.output_file.exists()


def test_apply_audio_effect_accepts_config_object(processor, media, tmp_path):
    config = AudioEffectConfig(**{"type": "chipmunk"})
    result = processor.apply_audio_effect(str(media), str(tmp_path / "o.mp4"), config)
    assert "-af" in result.command


def test_identity_chain_still_reencodes_without_filter(processor, media, tmp_path):
    # apply_effects with an all-identity chain must not pass -af but still runs.
    result = apply_effects(processor.runner, str(media), str(tmp_path / "o.mp4"),
                           AudioEffectConfig(effects=[AudioEffect(type="volume", gain=0)]),
                           encode=processor._encode())
    assert "-af" not in result.command
    assert result.output_file.exists()


# --- real FFmpeg integration ------------------------------------------------

@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg integration binaries are unavailable")
@pytest.mark.parametrize("options", [
    {"type": "normalize"},
    {"type": "bass", "gain": 6},
    {"type": "treble", "gain": 4},
    {"type": "volume", "gain": 3},
    {"type": "pitch", "semitones": 3},
    {"type": "deep_voice"},
    {"type": "chipmunk"},
    {"type": "echo"},
    {"type": "speed", "factor": 1.5},
    {"effects": [{"type": "normalize"}, {"type": "bass"}, {"type": "volume", "gain": 4}]},
])
def test_audio_effects_run_under_real_ffmpeg(tmp_path, options):
    """Each documented effect (and a chain) must encode a valid output."""
    source = tmp_path / "tone.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-f", "lavfi", "-i", "color=c=black:s=160x120:d=2",
         "-map", "1:v", "-map", "0:a", "-c:v", "libx264", "-shortest", str(source)],
        check=True, capture_output=True,
    )
    processor = Processor(load_config("settings.yaml"))
    result = processor.apply_audio_effect(str(source), str(tmp_path / "out.mp4"), options)
    assert result.output_file.stat().st_size > 0
    info = processor.inspect(str(result.output_file))
    assert info.has_audio
