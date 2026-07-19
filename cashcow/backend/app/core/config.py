"""Application configuration.

Central place for values that main.py and the API layer read, so those
modules never carry hard-coded literals.
"""

import os
from typing import Final

# Application version, surfaced by the /health endpoint.
VERSION: Final[str] = "0.1.0"

# Origins allowed to call this API. The Next.js dev server runs on port 3000.
CORS_ORIGINS: Final[list[str]] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean env var (``1/true/yes/on`` truthy), else the default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class DownloaderConfig:
    """Downloader hardening options, in one place.

    Recent YouTube anti-bot changes require yt-dlp to authenticate with browser
    cookies and run a remote challenge solver. These settings are applied
    transparently to every yt-dlp call the backend makes (the job downloader and
    the trim-slider metadata pre-fetch), so users never pass CLI flags.

    Defaults match the flags YouTube currently expects
    (``--cookies-from-browser chrome`` and ``--remote-components ejs:github``);
    each is overridable by environment variable for deployments where, say, a
    different browser holds the login or the challenge solver is disabled.
    """

    # Browser whose cookie store yt-dlp reads (chrome, firefox, edge, brave, …).
    BROWSER: Final[str] = os.getenv("CASHCOW_DL_BROWSER", "chrome")
    # Whether to attach browser cookies at all.
    USE_BROWSER_COOKIES: Final[bool] = _env_bool("CASHCOW_DL_USE_BROWSER_COOKIES", True)
    # Remote components to enable (comma-separated); "" disables them entirely.
    REMOTE_COMPONENTS: Final[list[str]] = [
        component.strip()
        for component in os.getenv("CASHCOW_DL_REMOTE_COMPONENTS", "ejs:github").split(",")
        if component.strip()
    ]


downloader_config = DownloaderConfig()
