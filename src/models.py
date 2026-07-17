"""Data models representing structures utilized within the system.

Defines the schema for DownloadResult and other media models.
"""

from typing import Optional
from pydantic import BaseModel, Field


class DownloadResult(BaseModel):
    """Pydantic model representing the result of a media download.

    This structured model is returned by the Downloader engine and consumed
    by subsequent platform phases.
    """
    success: bool = Field(..., description="Flag indicating if the download succeeded")
    url: str = Field(..., description="The original media URL targeted for download")
    title: Optional[str] = Field(default=None, description="Title of the video/media")
    duration: Optional[float] = Field(default=None, description="Duration in seconds")
    uploader: Optional[str] = Field(default=None, description="Creator/uploader name")
    file_path: Optional[str] = Field(default=None, description="Absolute local path to the downloaded media file")
    thumbnail_path: Optional[str] = Field(default=None, description="Absolute local path to the downloaded thumbnail image")
    description_path: Optional[str] = Field(default=None, description="Absolute local path to the saved description text file")
    subtitles: dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary mapping subtitle language codes to local file paths",
    )
    download_time: float = Field(default=0.0, description="Time taken to download in seconds")
    file_size: Optional[int] = Field(default=None, description="Downloaded media file size in bytes")
    error: Optional[str] = Field(default=None, description="Error message if success is False")
