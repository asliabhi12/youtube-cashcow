"""Lightweight video metadata pre-fetch for the trim slider.

The Home page's dual-handle trim slider needs the video's real duration before a
job runs, so its range reflects the actual clip length. This performs a
metadata-only ``yt-dlp`` lookup (``download=False``) and returns just the title
and duration. It lives in the backend (not the engine) and does not touch or
reconfigure the processing pipeline.

The call is network-dependent and can fail — an invalid URL, a private/removed
video, or (as in this sandbox) YouTube rejecting yt-dlp's client. Failures are
surfaced as typed exceptions so the route can distinguish a bad request from an
upstream extraction failure, and the frontend can fall back to a default range.
"""

from __future__ import annotations

from urllib.parse import urlparse

import yt_dlp

from app.services.downloader_hardening import apply_hardening

_SOCKET_TIMEOUT = 30


class InvalidVideoUrl(ValueError):
    """The supplied URL is empty or not a well-formed http(s) URL."""


class MetadataUnavailable(RuntimeError):
    """yt-dlp could not extract metadata (network, private video, blocked, …)."""


def _validate_url(url: str) -> None:
    """Reject empty or non-http(s) URLs before hitting the network.

    Mirrors the validation ``src.downloader.Downloader.validate_url`` applies, so
    a URL accepted here is one the downloader would also accept later.
    """
    if not url:
        raise InvalidVideoUrl("URL cannot be empty.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise InvalidVideoUrl(
            f"Invalid URL: '{url}'. Must be a fully formed HTTP or HTTPS address."
        )


def fetch_metadata(url: str) -> dict[str, object]:
    """Return ``{"title": str | None, "duration": float | None}`` for a video.

    ``duration`` is in seconds. Raises :class:`InvalidVideoUrl` for a malformed
    URL and :class:`MetadataUnavailable` when extraction fails for any reason.
    """
    _validate_url(url)

    opts = {
        "nocheckcertificate": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": _SOCKET_TIMEOUT,
    }
    # Same YouTube anti-bot hardening as the job downloader, so the trim-slider
    # pre-fetch doesn't hit the "confirm you're not a bot" wall the download would
    # otherwise clear. Logged by the downloader itself, so no per-lookup logging.
    apply_hardening(opts)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # yt-dlp raises many subtypes; treat all as upstream failure.
        raise MetadataUnavailable(str(exc)) from exc

    if not info:
        raise MetadataUnavailable(f"No metadata returned for: '{url}'")
    if info.get("_type") == "playlist" or "entries" in info:
        raise InvalidVideoUrl("The URL points to a playlist, not a single video.")

    duration = info.get("duration")
    return {
        "title": info.get("title"),
        "duration": float(duration) if isinstance(duration, (int, float)) else None,
    }
