"""Application configuration.

Central place for values that main.py and the API layer read, so those
modules never carry hard-coded literals.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Final, Optional

from app.core.environment import Environment, get_current_environment

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
    """Downloader hardening options."""

    BROWSER: Final[str] = os.getenv("CASHCOW_DL_BROWSER", "chrome")
    USE_BROWSER_COOKIES: Final[bool] = _env_bool("CASHCOW_DL_USE_BROWSER_COOKIES", True)
    REMOTE_COMPONENTS: Final[list[str]] = [
        component.strip()
        for component in os.getenv("CASHCOW_DL_REMOTE_COMPONENTS", "ejs:github").split(",")
        if component.strip()
    ]


downloader_config = DownloaderConfig()


DEFAULT_GEMINI_MODEL: Final[str] = "gemini-2.5-flash"

# Generic AI / LLM Configuration
AI_PROVIDER: Final[str] = (
    os.getenv("AI_PROVIDER") or os.getenv("LLM_PROVIDER") or "openai-oauth"
)
AI_BASE_URL: Final[str] = (
    os.getenv("AI_BASE_URL") or os.getenv("OPENAI_OAUTH_BASE_URL") or "http://127.0.0.1:10531/v1"
)
AI_MODEL: Final[str] = (
    os.getenv("AI_MODEL") or os.getenv("GPT_MODEL") or "gpt-5.6-sol"
)
AI_ENABLED: Final[bool] = _env_bool("AI_ENABLED", True)

# Backwards compatibility configuration names
OPENAI_OAUTH_BASE_URL: Final[str] = AI_BASE_URL
GPT_MODEL: Final[str] = AI_MODEL


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
    """YouTube upload defaults and OAuth settings."""

    ACCOUNT_ID: Final[str] = os.getenv("YOUTUBE_ACCOUNT_ID", "default")
    REDIRECT_URI: Final[str] = (
        get_config_value("YOUTUBE_REDIRECT_URI")
        or "http://localhost:8000/oauth/google/callback"
    )
    FRONTEND_DESTINATIONS_URL: Final[str] = (
        get_config_value("FRONTEND_DESTINATIONS_URL")
        or "http://localhost:3000/destinations"
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


# --- Production-Grade Immutable AppConfig ---

_PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class DatabaseConfig:
    sqlite_path: Path
    timeout: float = 5.0
    wal_mode: bool = True


@dataclass(frozen=True)
class StorageConfig:
    builtin_profiles_dir: Path
    custom_profiles_dir: Path
    settings_dir: Path
    uploads_dir: Path
    downloads_dir: Path
    logs_dir: Path
    temp_dir: Path


@dataclass(frozen=True)
class AppConfig:
    env: Environment
    db: DatabaseConfig
    storage: StorageConfig
    ai_provider: str = AI_PROVIDER
    ai_base_url: str = AI_BASE_URL
    ai_model: str = AI_MODEL
    ai_enabled: bool = AI_ENABLED

    @classmethod
    def load(cls, env: Optional[Environment] = None, base_dir: Optional[Path] = None) -> "AppConfig":
        active_env = env or get_current_environment()
        root = base_dir or _PROJECT_ROOT

        if active_env == Environment.TESTING:
            test_root = base_dir or root
            db_path = test_root / "test_cashcow.db"
            custom_dir = test_root / "profiles" / "custom"
            settings_dir = test_root
            uploads_dir = test_root / "uploads"
            downloads_dir = test_root / "downloads"
            logs_dir = test_root / "logs"
            temp_dir = test_root / "temp"
        elif active_env == Environment.PRODUCTION:
            db_path = root / "cashcow.db"
            custom_dir = root / "profiles" / "custom"
            settings_dir = root
            uploads_dir = root / "uploads"
            downloads_dir = root / "downloads"
            logs_dir = root / "logs"
            temp_dir = root / "temp"
        else:
            # Development environment default
            db_path = root / "cashcow_dev.db"
            custom_dir = root / "profiles" / "custom"
            settings_dir = root
            uploads_dir = root / "uploads"
            downloads_dir = root / "downloads"
            logs_dir = root / "logs"
            temp_dir = root / "temp"

        builtin_dir = _PROJECT_ROOT / "profiles"

        return cls(
            env=active_env,
            db=DatabaseConfig(sqlite_path=db_path),
            storage=StorageConfig(
                builtin_profiles_dir=builtin_dir,
                custom_profiles_dir=custom_dir,
                settings_dir=settings_dir,
                uploads_dir=uploads_dir,
                downloads_dir=downloads_dir,
                logs_dir=logs_dir,
                temp_dir=temp_dir,
            ),
        )


_global_config: Optional[AppConfig] = None


def get_app_config() -> AppConfig:
    global _global_config
    if _global_config is None:
        _global_config = AppConfig.load()
    return _global_config


def set_app_config(config: Optional[AppConfig]) -> None:
    global _global_config
    _global_config = config
