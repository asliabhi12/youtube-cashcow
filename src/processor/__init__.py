"""Reusable, YouTube-independent FFmpeg media processing APIs."""

from .exceptions import FFmpegError, FFmpegNotFoundError, InvalidMediaError, ProcessingCancelledError, ProcessingFailedError, ProcessingTimeoutError, UnsupportedCodecError
from .models import MaskConfig, OverlayConfig, ProcessingResult, VideoInfo
from .processor import Processor

__all__ = ["Processor", "VideoInfo", "ProcessingResult", "MaskConfig", "OverlayConfig", "FFmpegError", "FFmpegNotFoundError", "InvalidMediaError", "ProcessingCancelledError", "ProcessingFailedError", "ProcessingTimeoutError", "UnsupportedCodecError"]
