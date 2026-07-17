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
