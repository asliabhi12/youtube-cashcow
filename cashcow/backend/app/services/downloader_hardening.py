"""Shared yt-dlp hardening options for the backend's downloaders.

Recent YouTube anti-bot changes reject plain yt-dlp calls with "Sign in to
confirm you're not a bot". The fix is to authenticate with browser cookies and
enable a remote challenge solver — the CLI equivalents of
``--cookies-from-browser chrome`` and ``--remote-components ejs:github``.

Both of the backend's yt-dlp callers (the job downloader and the trim-slider
metadata pre-fetch) build their option dicts through :func:`apply_hardening`
here, so the anti-bot configuration lives in exactly one place and is read from
:mod:`app.core.config`. Nothing under ``src/`` is touched; the engine's
``Downloader`` is subclassed and this helper layers the extra options on top of
whatever options it already produces.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import downloader_config

logger = logging.getLogger(__name__)

# The clean, user-facing message for an auth / challenge-solving failure. The
# raw yt-dlp text (URLs, flags, tracebacks) is never surfaced to the user.
VERIFICATION_ERROR_MESSAGE = (
    "Unable to download this YouTube video. "
    "YouTube requested additional verification."
)

# Substrings (lower-cased) that mark a failure as an anti-bot / verification one
# rather than an ordinary unavailable/private/network error.
_VERIFICATION_MARKERS = (
    "sign in to confirm",
    "not a bot",
    "confirm you're not a bot",
    "confirm you are not a bot",
    "--cookies-from-browser",
    "--remote-components",
    "challenge",
)


def apply_hardening(opts: dict[str, Any], *, log_once: bool = False) -> dict[str, Any]:
    """Return ``opts`` with the configured anti-bot options merged in.

    Adds ``cookiesfrombrowser`` when browser cookies are enabled and
    ``remote_components`` when any are configured. The dict is mutated in place
    and also returned for convenience. When ``log_once`` is true, emits the
    one-line "using …" messages — callers pass it exactly once per download so
    the lines don't repeat for every internal yt-dlp call.
    """
    if downloader_config.USE_BROWSER_COOKIES:
        # yt-dlp expects a tuple; the first element is the browser name.
        opts["cookiesfrombrowser"] = (downloader_config.BROWSER,)
        if log_once:
            logger.info("Using browser cookies: %s", downloader_config.BROWSER)

    if downloader_config.REMOTE_COMPONENTS:
        opts["remote_components"] = list(downloader_config.REMOTE_COMPONENTS)
        if log_once:
            logger.info(
                "Using EJS remote challenge solver (%s)",
                ", ".join(downloader_config.REMOTE_COMPONENTS),
            )

    return opts


def is_verification_error(message: str) -> bool:
    """Whether a yt-dlp error message indicates an anti-bot / verification wall."""
    lowered = message.lower()
    return any(marker in lowered for marker in _VERIFICATION_MARKERS)
