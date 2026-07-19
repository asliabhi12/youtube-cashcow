"""A backend downloader that applies YouTube anti-bot hardening to yt-dlp.

The engine's ``src.downloader.Downloader`` is production code we must not modify,
but ``PipelineRunner`` accepts an injected ``downloader``. This subclass layers
the configured hardening options (browser cookies + remote challenge solver) on
top of every option dict the base downloader builds, logs the hardening once per
download, and converts a raw anti-bot failure into a clean application error —
without changing anything under ``src/``.

The workflow adapter injects an instance of this into the runner, so real jobs
download through it while the engine itself stays untouched.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# The engine lives in ``src/`` at the repo root, above the backend package. Put
# the root on the import path before importing it, so this module is safe to
# import in any order (not only after ``workflow.py`` has done the same).
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.downloader import Downloader  # noqa: E402
from src.models import DownloadResult  # noqa: E402

from app.services.downloader_hardening import (  # noqa: E402
    VERIFICATION_ERROR_MESSAGE,
    apply_hardening,
    is_verification_error,
)

logger = logging.getLogger(__name__)


class HardenedDownloader(Downloader):
    """``Downloader`` with YouTube anti-bot options applied transparently.

    Overrides only the two option-building seams and the public
    ``download_video`` result handling; all download logic, path resolution, and
    metadata handling are inherited unchanged.
    """

    def _build_ydl_options(self, progress_hook=None) -> dict[str, Any]:
        """Base download options plus the configured hardening and subtitle options."""
        opts = super()._build_ydl_options(progress_hook)
        # Request English and Hindi subtitles so the workflow can extract a
        # transcript for metadata enrichment. Both manual and auto-generated
        # captions are enabled for maximum coverage.
        opts["subtitleslangs"] = ["en", "hi"]
        opts["subtitlesformat"] = "srt"
        opts["writeautomaticsub"] = True
        # Logging happens once in ``download_video`` (this seam may be reached by
        # more than one code path), so suppress per-call logging here.
        return apply_hardening(opts, log_once=False)

    def _extract_info(self, url: str, **extra_opts: Any) -> dict[str, Any]:
        """Metadata extraction with hardening applied (covers the playlist path)."""
        return super()._extract_info(url, **apply_hardening(dict(extra_opts)))

    def download_video(self, url: str, progress=None, task_id=None) -> DownloadResult:
        """Download a video, hardened, with a clean error on a verification wall.

        Emits the "using …" hardening lines exactly once, delegates the actual
        download to the base implementation, and — if it fails specifically
        because YouTube demanded verification — replaces the raw yt-dlp text
        (URLs, flags, traceback fragments) with a clean, user-facing message. The
        original detail is kept in debug logs only.
        """
        # One pair of hardening log lines per download, before any yt-dlp work.
        apply_hardening({}, log_once=True)

        result = super().download_video(url, progress=progress, task_id=task_id)

        if not result.success and result.error and is_verification_error(result.error):
            # Keep the raw yt-dlp detail for operators, but never show it to users.
            logger.debug("Raw yt-dlp verification failure for '%s': %s", url, result.error)
            result.error = VERIFICATION_ERROR_MESSAGE

        return result
