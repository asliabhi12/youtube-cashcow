"""Typed exceptions for performance-layer failures."""


class PerformanceError(Exception):
    """Base error for hardware selection and benchmarking."""


class HardwareDetectionError(PerformanceError):
    """FFmpeg capabilities could not be inspected."""


class EncoderUnavailableError(PerformanceError):
    """No suitable encoder is available under the requested policy."""
