"""Application configuration.

Central place for values that main.py and the API layer read, so those
modules never carry hard-coded literals.
"""

import os
from pathlib import Path
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


DEFAULT_GEMINI_MODEL: Final[str] = "gemini-2.5-flash"


def get_config_value(name: str) -> str | None:
    """Read an env var, falling back to local .env files."""
    value = os.getenv(name)
    if value:
        return value
    return _read_dotenv().get(name)


def _read_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in _dotenv_paths():
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            key, value = _parse_dotenv_line(line)
            if key and key not in values:
                values[key] = value
    return values


def _dotenv_paths() -> list[Path]:
    backend_root = Path(__file__).resolve().parents[2]
    repo_root = Path(__file__).resolve().parents[4]
    return [backend_root / ".env", repo_root / ".env"]


def _parse_dotenv_line(line: str) -> tuple[str | None, str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None, ""
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    return (key or None), value


class YouTubeUploadConfig:
    """YouTube upload defaults and OAuth settings.

    The default account is represented by OAuth client credentials plus a refresh
    token. Keeping the account id explicit makes the service shape ready for
    additional accounts later without adding user/account management now.
    """

    ACCOUNT_ID: Final[str] = os.getenv("YOUTUBE_ACCOUNT_ID", "default")
    REDIRECT_URI: Final[str] = (
        get_config_value("YOUTUBE_REDIRECT_URI")
        or "http://localhost:8000/youtube/auth/callback"
    )
    TOKEN_URI: Final[str] = os.getenv(
        "YOUTUBE_TOKEN_URI",
        "https://oauth2.googleapis.com/token",
    )
    RESUMABLE_UPLOAD_URL: Final[str] = os.getenv(
        "YOUTUBE_RESUMABLE_UPLOAD_URL",
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
    )
    PRIVACY_STATUS: Final[str] = os.getenv("YOUTUBE_PRIVACY_STATUS", "private")
    CATEGORY_ID: Final[str] = os.getenv("YOUTUBE_CATEGORY_ID", "22")
    MADE_FOR_KIDS: Final[bool] = _env_bool("YOUTUBE_MADE_FOR_KIDS", False)


youtube_upload_config = YouTubeUploadConfig()


def set_local_config_value(name: str, value: str) -> None:
    """Persist one local secret/config value in the backend .env file.

    This is intentionally small and only used for the MVP YouTube OAuth refresh
    token. Environment variables still take precedence on reads.
    """
    path = _dotenv_paths()[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    rendered = f'{name}="{_escape_dotenv_value(value)}"'
    for index, line in enumerate(lines):
        key, _ = _parse_dotenv_line(line)
        if key == name:
            lines[index] = rendered
            break
    else:
        lines.append(rendered)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _escape_dotenv_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
