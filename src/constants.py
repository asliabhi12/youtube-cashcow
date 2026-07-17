"""Module containing global constants for the YouTube CashCow application.

This module centralizes all constant values used throughout the application to avoid
magic numbers and hardcoding.
"""

from typing import Final

# Application Meta
APP_NAME: Final[str] = "YouTube CashCow"
VERSION: Final[str] = "1.0.0"
MIN_PYTHON_VERSION: Final[tuple[int, int]] = (3, 12)

# File Paths & Config Defaults
DEFAULT_SETTINGS_FILE: Final[str] = "settings.yaml"
DEFAULT_ENV_FILE: Final[str] = ".env"

# Storage Settings
DEFAULT_DOWNLOAD_FOLDER: Final[str] = "downloads"
DEFAULT_TEMP_FOLDER: Final[str] = "temp"
DEFAULT_OUTPUT_FOLDER: Final[str] = "output"
DEFAULT_LOG_FOLDER: Final[str] = "logs"
DEFAULT_ASSETS_FOLDER: Final[str] = "assets"

# Required Directory Trees
REQUIRED_DIRECTORIES: Final[list[str]] = [
    DEFAULT_DOWNLOAD_FOLDER,
    DEFAULT_TEMP_FOLDER,
    DEFAULT_OUTPUT_FOLDER,
    DEFAULT_LOG_FOLDER,
    DEFAULT_ASSETS_FOLDER,
    f"{DEFAULT_ASSETS_FOLDER}/overlays",
    f"{DEFAULT_ASSETS_FOLDER}/logos",
    f"{DEFAULT_ASSETS_FOLDER}/masks",
    f"{DEFAULT_ASSETS_FOLDER}/intro",
    f"{DEFAULT_ASSETS_FOLDER}/outro",
]

# File Extension Configurations
SUPPORTED_VIDEO_EXTENSIONS: Final[set[str]] = {".mp4", ".mkv", ".mov", ".avi"}
SUPPORTED_AUDIO_EXTENSIONS: Final[set[str]] = {".mp3", ".wav", ".aac", ".m4a"}
SUPPORTED_IMAGE_EXTENSIONS: Final[set[str]] = {".png", ".jpg", ".jpeg"}

# Logging Constants
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
