"""Pydantic models shared by FFmpeg processing operations."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class VideoInfo(BaseModel):
    """Typed media details reported by FFprobe."""

    path: Path
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    duration: Optional[float] = None
    bitrate: Optional[int] = None
    codec: Optional[str] = None
    audio_codec: Optional[str] = None
    has_audio: bool = False


class ProcessingResult(BaseModel):
    """Successful FFmpeg operation output and execution details."""

    output_file: Path
    duration: float = Field(ge=0)
    command: list[str]
    stderr: str = ""
