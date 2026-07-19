"""Unit tests for the configuration system and YAML loader."""

import pytest
from src.config import load_config, Settings
from src.exceptions import ConfigurationError


def test_load_valid_config():
    """Verify that settings.yaml can be successfully loaded and validated."""
    # Assuming settings.yaml exists and is valid in the root directory
    settings = load_config("settings.yaml")
    assert isinstance(settings, Settings)
    assert settings.app.name == "YouTube CashCow"
    assert settings.app.version == "1.0.0"
    assert settings.logging.level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def test_load_nonexistent_config():
    """Verify that loading a non-existent configuration file raises ConfigurationError."""
    with pytest.raises(ConfigurationError) as exc_info:
        load_config("nonexistent_settings.yaml")
    assert "Configuration file not found" in str(exc_info.value)


def test_ffmpeg_encoding_defaults():
    """The shipped settings expose the new encoding schema with sane defaults."""
    ffmpeg = load_config("settings.yaml").ffmpeg
    assert ffmpeg.audio_bitrate == "192k"
    assert ffmpeg.video_bitrate in (None, "4000k")
    assert ffmpeg.codec in ("auto", "h264_videotoolbox")
    assert ffmpeg.crf == 23


def test_legacy_bitrate_key_still_loads(tmp_path):
    """Existing settings.yaml files using the old `bitrate` key stay valid."""
    legacy = tmp_path / "settings.yaml"
    legacy.write_text(
        "app:\n  name: Legacy\n  version: '1.0.0'\n"
        "logging:\n  level: INFO\n"
        "storage:\n  download_dir: downloads\n"
        "ffmpeg:\n  codec: libx264\n  bitrate: 256k\n"
    )
    ffmpeg = load_config(str(legacy)).ffmpeg
    assert ffmpeg.audio_bitrate == "256k"  # old key mapped onto the new field
    assert ffmpeg.video_bitrate is None


def test_video_bitrate_is_configurable(tmp_path):
    """A specified video_bitrate is parsed and preserved."""
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        "app:\n  name: BR\n  version: '1.0.0'\n"
        "logging:\n  level: INFO\n"
        "storage:\n  download_dir: downloads\n"
        "ffmpeg:\n  video_bitrate: 8M\n  audio_bitrate: 320k\n"
    )
    ffmpeg = load_config(str(cfg)).ffmpeg
    assert ffmpeg.video_bitrate == "8M"
    assert ffmpeg.audio_bitrate == "320k"
