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
            raise ProcessingFailedError(f"FFmpeg processing failed: {detail}")
        self.logger.info("FFmpeg command completed in %.2fs", elapsed)
        return stdout, stderr, elapsed
