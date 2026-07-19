"""Backend-owned application settings, persisted to ``settings.json``.

This is deliberately separate from the engine's ``settings.yaml`` (which
configures ffmpeg, storage paths, yt-dlp, etc. and is never written by the app).
The only thing stored here today is the last profile the user ran, so the Home
page can re-open it automatically on the next visit.

Reads tolerate a missing or corrupt file by returning defaults — the app must
start even with no settings yet. Writes are atomic (temp file + ``os.replace``)
under a module lock, so a concurrent read never observes a half-written file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import Lock

from pydantic import BaseModel

# The settings file lives at the repository root, alongside ``settings.yaml``.
# ``parents[4]`` walks up services → app → backend → cashcow → repo root, the
# same anchor ``workflow.py`` uses.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SETTINGS_FILE = _PROJECT_ROOT / "settings.json"

_lock = Lock()


class AppSettings(BaseModel):
    """Application-level settings surfaced by GET /settings.

    ``last_profile`` is the id of the profile most recently used to run a job.
    It is reported as ``None`` when unset *or* when it no longer resolves to an
    existing profile (see ``app.api.profiles``), so a stale pointer never breaks
    the Home page.
    """

    last_profile: str | None = None


def get_app_settings() -> AppSettings:
    """Return the current settings, or defaults if the file is absent/unreadable."""
    with _lock:
        return _read_unlocked()


def set_last_profile(profile_id: str | None) -> AppSettings:
    """Record the last-used profile id and persist it. Returns the new settings.

    Passing ``None`` clears the pointer.
    """
    with _lock:
        settings = _read_unlocked()
        settings.last_profile = profile_id
        _write_unlocked(settings)
        return settings


def _read_unlocked() -> AppSettings:
    """Load settings from disk, falling back to defaults on any error.

    Caller must hold ``_lock``.
    """
    try:
        raw = _SETTINGS_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return AppSettings()
    try:
        return AppSettings.model_validate_json(raw)
    except ValueError:
        # Corrupt or hand-edited into an invalid shape: start clean rather than
        # crash. The next write overwrites it.
        return AppSettings()


def _write_unlocked(settings: AppSettings) -> None:
    """Atomically write settings to disk. Caller must hold ``_lock``."""
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file in the same directory, then atomically replace the
    # target so readers only ever see a complete file.
    fd, tmp_path = tempfile.mkstemp(dir=str(_SETTINGS_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(settings.model_dump_json(indent=2))
        os.replace(tmp_path, _SETTINGS_FILE)
    except BaseException:
        # Don't leave a stray temp file behind if the write or replace fails.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
