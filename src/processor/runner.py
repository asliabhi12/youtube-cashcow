"""The sole subprocess boundary for FFmpeg and FFprobe commands."""

import logging
import subprocess
import time
from pathlib import Path
from threading import Event
from typing import Callable, Sequence

from .exceptions import (
    FFmpegNotFoundError,
    ProcessingCancelledError,
    ProcessingFailedError,
    ProcessingTimeoutError,
)

ProgressCallback = Callable[[float], None]


class FFmpegRunner:
    """Run commands safely, with normalized errors and optional progress hooks."""

    def __init__(self, executable: str, timeout: int, logger: logging.Logger, hwaccel: str | None = None) -> None:
        self.executable = executable
        self.timeout = timeout
        self.logger = logger
        self.hwaccel = hwaccel

    def run(
        self,
        args: Sequence[str],
        *,
        timeout: int | None = None,
        cancel_event: Event | None = None,
        progress: ProgressCallback | None = None,
        _allow_software_fallback: bool = True,
    ) -> tuple[str, str, float]:
        """Execute arguments without a shell and return stdout, stderr, elapsed seconds."""
        acceleration = ["-hwaccel", self.hwaccel] if self.hwaccel else []
        command = [self.executable, *acceleration, *map(str, args)]
        started = time.monotonic()
        self.logger.debug("Executing FFmpeg command: %s", command)
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, universal_newlines=True,
            )
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError(f"FFmpeg executable not found: {self.executable}") from exc
        limit = timeout or self.timeout
        while process.poll() is None:
            if cancel_event and cancel_event.is_set():
                process.kill()
                process.communicate()
                raise ProcessingCancelledError("FFmpeg processing was cancelled")
            if time.monotonic() - started > limit:
                process.kill()
                process.communicate()
                raise ProcessingTimeoutError(f"FFmpeg processing exceeded {limit} seconds")
            time.sleep(0.05)
        stdout, stderr = process.communicate()
        elapsed = time.monotonic() - started
        if progress:
            progress(1.0)
        if process.returncode:
            detail = stderr.strip()[-1000:] or "FFmpeg returned no diagnostic output"
            self.logger.error("FFmpeg command failed (%s): %s", process.returncode, detail)
            fallback = _software_fallback_args(args) if _allow_software_fallback else None
            if fallback:
                self.logger.warning("Hardware encoder failed; retrying once with software fallback")
                return self.run(
                    fallback, timeout=timeout, cancel_event=cancel_event, progress=progress,
                    _allow_software_fallback=False,
                )
            raise ProcessingFailedError(f"FFmpeg processing failed: {detail}")
        self.logger.info("FFmpeg command completed in %.2fs", elapsed)
        return stdout, stderr, elapsed


def _software_fallback_args(args: Sequence[str]) -> list[str] | None:
    """Replace a failed hardware video encoder without leaking FFmpeg logic upward."""
    values = list(map(str, args))
    try:
        index = values.index("-c:v") + 1
    except ValueError:
        return None
    replacements = {
        "h264_videotoolbox": "libx264", "hevc_videotoolbox": "libx265",
        "h264_nvenc": "libx264", "hevc_nvenc": "libx265", "av1_nvenc": "libsvtav1",
        "h264_qsv": "libx264", "hevc_qsv": "libx265",
    }
    replacement = replacements.get(values[index])
    if not replacement:
        return None
    values[index] = replacement
    # VideoToolbox's quality knob is not recognized by software encoders.
    while "-q:v" in values:
        quality = values.index("-q:v")
        del values[quality:quality + 2]
    if "-preset" not in values:
        values.extend(["-preset", "medium"])
    return values
