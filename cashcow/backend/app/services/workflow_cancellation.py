"""Cooperative cancellation helpers for the existing workflow adapter."""

from __future__ import annotations

from pathlib import Path
import sys
from threading import Event
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.processor import Processor  # noqa: E402
from src.processor.models import AudioEffectConfig, ColorEffectConfig, OverlayConfig, ProcessingResult  # noqa: E402

from app.services.hardened_downloader import HardenedDownloader  # noqa: E402


class WorkflowCancelledError(RuntimeError):
    """Raised when a job has been cooperatively cancelled."""


class CancellableDownloader(HardenedDownloader):
    """Hardened downloader that aborts through yt-dlp's progress hook."""

    def __init__(self, settings, cancel_event: Event) -> None:
        super().__init__(settings)
        self._cancel_event = cancel_event

    def _build_ydl_options(self, progress_hook=None) -> dict[str, Any]:
        def cancellable_hook(event: dict[str, Any]) -> None:
            if self._cancel_event.is_set():
                raise WorkflowCancelledError("Job cancellation requested")
            if progress_hook is not None:
                progress_hook(event)

        return super()._build_ydl_options(cancellable_hook)


class CancellableProcessor(Processor):
    """Processor wrapper that passes the workflow cancel event into FFmpeg calls."""

    def __init__(self, settings, cancel_event: Event) -> None:
        super().__init__(settings)
        self._cancel_event = cancel_event

    def _with_cancel(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        kwargs.setdefault("cancel_event", self._cancel_event)
        return kwargs

    def trim(self, input_file: str, output_file: str, start: float, end: float, **kwargs) -> ProcessingResult:
        return super().trim(input_file, output_file, start, end, **self._with_cancel(kwargs))

    def resize(self, input_file: str, output_file: str, width: int | None = None, height: int | None = None, **kwargs) -> ProcessingResult:
        return super().resize(input_file, output_file, width, height, **self._with_cancel(kwargs))

    def overlay(self, input_file: str, image_file: str, output_file: str, x: str | int = 0, y: str | int = 0, **kwargs) -> ProcessingResult:
        return super().overlay(input_file, image_file, output_file, x, y, **self._with_cancel(kwargs))

    def composite(self, input_file: str, output_file: str, config: OverlayConfig | dict, **kwargs) -> ProcessingResult:
        return super().composite(input_file, output_file, config, **self._with_cancel(kwargs))

    def apply_audio_effect(self, input_file: str, output_file: str, config: AudioEffectConfig | dict, **kwargs) -> ProcessingResult:
        return super().apply_audio_effect(input_file, output_file, config, **self._with_cancel(kwargs))

    def apply_color_effect(self, input_file: str, output_file: str, config: ColorEffectConfig | dict, **kwargs) -> ProcessingResult:
        return super().apply_color_effect(input_file, output_file, config, **self._with_cancel(kwargs))
