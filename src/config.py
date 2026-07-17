"""Configuration system for YouTube CashCow.

Loads settings from settings.yaml and validates them using Pydantic models.
Raises custom exceptions for validation errors.
"""

from pathlib import Path
from typing import Any, Optional
import yaml
from pydantic import BaseModel, Field, ValidationError

from src.exceptions import ConfigurationError
from src.utils import resolve_path


class AppConfig(BaseModel):
    """General application metadata and debug settings."""
    name: str = Field(..., min_length=1, description="Application name")
    version: str = Field(..., min_length=1, description="Application version")
    debug: bool = Field(default=False, description="Debug mode flag")


class LoggingConfig(BaseModel):
    """Logging destination and severity configurations."""
    level: str = Field(default="INFO", description="Default logging severity level")
    console_output: bool = Field(default=True, description="Enable console logging output")
    file_output: bool = Field(default=True, description="Enable file logging output")
    log_dir: str = Field(default="logs", description="Directory to store log files")


class StorageConfig(BaseModel):
    """Storage directory configurations for file output and manipulation."""
    download_dir: str = Field(default="downloads", description="Path to download raw videos")
    temp_dir: str = Field(default="temp", description="Path for temp operations")
    output_dir: str = Field(default="output", description="Path to output completed products")
    assets_dir: str = Field(default="assets", description="Path to static overlays/logos assets")


class FFmpegConfig(BaseModel):
    """FFmpeg executable and default encoding configuration."""
    path: str = Field(default="ffmpeg", description="Path or command to run FFmpeg")
    executable: Optional[str] = Field(default=None, description="Explicit FFmpeg command; overrides path")
    ffprobe: str = Field(default="ffprobe", description="Path or command to run FFprobe")
    timeout: int = Field(default=3600, gt=0, description="Maximum processing time in seconds")
    threads: str | int = Field(default="auto", description="FFmpeg thread count or auto")
    hwaccel: Optional[str] = Field(default=None, description="Optional FFmpeg hardware acceleration method")
    codec: str = Field(default="libx264", description="Video codec for rendering")
    preset: str = Field(default="medium", description="FFmpeg speed preset")
    crf: int = Field(default=23, ge=0, le=51, description="Constant Rate Factor quality (0-51)")
    audio_codec: str = Field(default="aac", description="Audio codec for rendering")
    bitrate: str = Field(default="192k", description="Audio encoding bitrate")


class YtDlpConfig(BaseModel):
    """yt-dlp video downloader placeholder configuration."""
    format: str = Field(default="best", description="yt-dlp download format string")
    merge_output_format: str = Field(default="mp4", description="Format to merge stream outputs")
    retries: int = Field(default=3, ge=0, description="Download retry limit")
    rate_limit: Optional[str] = Field(default=None, description="Download rate limit (e.g. 50K)")


class YoutubeUploadConfig(BaseModel):
    """YouTube-specific API upload criteria placeholder configuration."""
    privacy_status: str = Field(default="private", description="Upload visibility setting")
    made_for_kids: bool = Field(default=False, description="Flag indicating child-safety class")
    category_id: str = Field(default="22", description="YouTube category ID")


class UploadConfig(BaseModel):
    """Multi-platform upload parameters configuration."""
    youtube: YoutubeUploadConfig = Field(default_factory=YoutubeUploadConfig)


class DownloadConfig(BaseModel):
    """Media download configurations using yt-dlp."""
    quality: str = Field(default="bestvideo+bestaudio", description="yt-dlp quality selection")
    format: str = Field(default="mp4", description="Output video format")
    output_directory: str = Field(default="downloads/", description="Target download folder")
    playlist: bool = Field(default=False, description="Allow downloading whole playlist")
    write_thumbnail: bool = Field(default=False, description="Save thumbnail images")
    write_description: bool = Field(default=False, description="Save description info to disk")
    write_subtitles: bool = Field(default=False, description="Save subtitles track")
    retries: int = Field(default=3, ge=0, description="Download connection retry count")
    concurrent_downloads: int = Field(default=2, ge=1, description="Parallel download workers")
    overwrite: bool = Field(default=False, description="Overwrite pre-existing outputs")


class PipelineConfig(BaseModel):
    """Defaults used by the workflow orchestration layer."""
    workspace: str = Field(default="workspace", description="Directory containing per-run workspaces")
    cleanup: bool = Field(default=True, description="Remove successful run workspaces")
    retries: int = Field(default=0, ge=0, description="Default retries for recoverable step failures")


class Settings(BaseModel):
    """Root configuration model representing the settings.yaml layout."""
    app: AppConfig
    logging: LoggingConfig
    storage: StorageConfig
    ffmpeg: FFmpegConfig = Field(default_factory=FFmpegConfig)
    yt_dlp: YtDlpConfig = Field(default_factory=YtDlpConfig)
    upload: UploadConfig = Field(default_factory=UploadConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)



def load_config(config_path: str = "settings.yaml") -> Settings:
    """Load configuration from a YAML file and validate it using Pydantic.

    Args:
        config_path: Path to the settings YAML file.

    Returns:
        Settings: The validated configuration object.

    Raises:
        ConfigurationError: If the file is missing, contains invalid YAML,
                            or fails Pydantic validation.
    """
    resolved_path = resolve_path(config_path)
    
    if not resolved_path.exists():
        raise ConfigurationError(
            f"Configuration file not found at: {resolved_path}. "
            f"Please ensure '{config_path}' exists in the application root."
        )

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(
            f"Failed to parse settings file '{resolved_path}' as YAML: {e}"
        ) from e
    except Exception as e:
        raise ConfigurationError(
            f"Error reading settings file '{resolved_path}': {e}"
        ) from e

    if raw_data is None:
        raise ConfigurationError(
            f"Configuration file at '{resolved_path}' is empty."
        )

    try:
        return Settings(**raw_data)
    except ValidationError as e:
        # Construct a detailed error report from Pydantic's validation errors
        error_messages = []
        for error in e.errors():
            loc = " -> ".join(str(field) for field in error["loc"])
            msg = error["msg"]
            error_messages.append(f"  [{loc}]: {msg}")
        
        details = "\n".join(error_messages)
        raise ConfigurationError(
            f"Configuration validation failed for '{resolved_path}':\n{details}"
        ) from e
