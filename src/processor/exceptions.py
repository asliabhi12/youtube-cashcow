"""Typed errors raised by the local-media FFmpeg processing layer."""

from src.exceptions import CashCowError


class FFmpegError(CashCowError):
    """Base class for processor errors."""


class FFmpegNotFoundError(FFmpegError):
    """Raised when FFmpeg or FFprobe is unavailable."""


class InvalidMediaError(FFmpegError):
    """Raised when an input media file is missing or cannot be inspected."""


class ProcessingFailedError(FFmpegError):
    """Raised when FFmpeg exits unsuccessfully."""


class ProcessingTimeoutError(FFmpegError):
    """Raised when a media command exceeds its configured timeout."""


class ProcessingCancelledError(FFmpegError):
    """Raised when a caller cancels an in-flight operation."""


class UnsupportedCodecError(FFmpegError):
    """Raised when a requested codec or concat inputs are incompatible."""
