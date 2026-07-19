"""Overlay-asset storage and management.

Overlay assets (the images/videos an overlay composites onto the frame) live on
disk under the repository root, split into two directories that mirror the
profile system's built-in/custom split:

* ``assets/overlays/built-in/`` — assets bundled with the app. Read-only: they
  can be picked but never overwritten or deleted.
* ``assets/overlays/user/`` — assets the user uploads. Deletable.

A profile only ever stores an asset's **bare filename** (never a path); the
workflow adapter resolves that filename to an absolute path by searching both
directories (see ``app.services.workflow._resolve_overlay_asset``). Keeping the
two roots separate means ``delete_asset`` can only ever touch the user directory
— a built-in can never be removed by structure, not just by a name check.

Uploads validate the extension against an allow-list and sanitize the filename
(no path separators, no traversal) before writing atomically (temp file +
``os.replace``) under a module lock, so a concurrent read never sees a partial
file and a malicious name can never escape the assets directory.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from threading import Lock

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Repository root, resolved like the other services:
# services → app → backend → cashcow → repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_OVERLAY_DIR = _PROJECT_ROOT / "assets" / "overlays"
BUILTIN_DIR = _OVERLAY_DIR / "built-in"
USER_DIR = _OVERLAY_DIR / "user"

# Extensions the engine's overlay compositor can load (images and short video
# clips). Anything else is rejected up front rather than failing mid-pipeline.
_ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".mp4",
    ".mov",
    ".webm",
}

# Cap the stored file size so an upload can't exhaust the disk. Overlay assets
# are small images or short clips; 50 MiB is generous headroom.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# A safe filename: letters, digits, spaces, dots, underscores and hyphens only.
# Everything else (path separators, control chars, shell metacharacters) is
# stripped, so a name can never traverse out of the assets directory.
_ILLEGAL_NAME_CHARS = re.compile(r"[^A-Za-z0-9 ._-]+")
_MAX_NAME_STEM = 120

_lock = Lock()


class AssetError(Exception):
    """Base class for asset-management errors."""


class AssetNotFoundError(AssetError):
    """Raised when an asset filename does not resolve to a user asset."""


class AssetReadOnlyError(AssetError):
    """Raised on an attempt to delete a built-in asset."""


class AssetValidationError(AssetError):
    """Raised when an upload fails validation (extension, name, or size)."""


class AssetSummary(BaseModel):
    """A selectable overlay asset for the picker.

    ``name`` is the bare filename a profile stores. ``builtin`` distinguishes
    bundled assets (read-only) from uploaded ones (deletable).
    """

    name: str
    builtin: bool


# --- Reads -----------------------------------------------------------------


def list_assets() -> list[AssetSummary]:
    """Return every overlay asset, built-ins first then user uploads.

    A user upload whose name collides with a built-in is skipped with a warning,
    matching the profile loader: built-ins always win so the resolved path is
    unambiguous.
    """
    summaries: list[AssetSummary] = []
    seen: set[str] = set()

    for path in _list_dir(BUILTIN_DIR):
        summaries.append(AssetSummary(name=path.name, builtin=True))
        seen.add(path.name)

    for path in _list_dir(USER_DIR):
        if path.name in seen:
            logger.warning("User asset '%s' shadows a built-in; skipping", path.name)
            continue
        summaries.append(AssetSummary(name=path.name, builtin=False))
        seen.add(path.name)

    return summaries


def asset_exists(name: str) -> bool:
    """Whether ``name`` resolves to a known overlay asset in either directory."""
    return resolve_path(name) is not None


def resolve_path(name: str) -> Path | None:
    """Return the absolute path of an asset by bare filename, or ``None``.

    Built-ins take precedence over a user file of the same name. The name is
    sanitized first so a traversal attempt (``../foo``) can never resolve to a
    file outside the two asset directories.
    """
    safe = _safe_name(name)
    if safe is None:
        return None
    builtin = BUILTIN_DIR / safe
    if builtin.is_file():
        return builtin
    user = USER_DIR / safe
    if user.is_file():
        return user
    return None


# --- Writes ----------------------------------------------------------------


def save_upload(filename: str, data: bytes) -> AssetSummary:
    """Store an uploaded overlay asset and return its summary.

    Validates the extension and size, sanitizes the filename (rejecting path
    separators), and makes the name unique across *both* directories so an
    upload never shadows a built-in or clobbers an existing user asset. Written
    atomically under the module lock.
    """
    if len(data) == 0:
        raise AssetValidationError("uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise AssetValidationError(
            f"file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB limit"
        )

    safe = _safe_name(filename)
    if safe is None:
        raise AssetValidationError("filename is empty or contains no usable characters")

    suffix = Path(safe).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise AssetValidationError(
            f"unsupported file type '{suffix or filename}'; "
            f"allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )

    with _lock:
        USER_DIR.mkdir(parents=True, exist_ok=True)
        unique = _unique_name(safe)
        target = USER_DIR / unique
        fd, tmp_path = tempfile.mkstemp(dir=str(USER_DIR), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp_path, target)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return AssetSummary(name=unique, builtin=False)


def delete_asset(name: str) -> None:
    """Delete a user-uploaded overlay asset.

    Raises :class:`AssetReadOnlyError` for a built-in and
    :class:`AssetNotFoundError` if no user asset by that name exists. By
    construction this can only ever unlink a file inside ``USER_DIR``.
    """
    safe = _safe_name(name)
    if safe is None:
        raise AssetNotFoundError(f"Asset '{name}' not found")
    with _lock:
        # A built-in of this name is protected even if a user file shadows it.
        if (BUILTIN_DIR / safe).is_file():
            raise AssetReadOnlyError(f"Asset '{safe}' is built-in and read-only")
        path = USER_DIR / safe
        if not path.is_file():
            raise AssetNotFoundError(f"Asset '{safe}' not found")
        path.unlink()


# --- Internals -------------------------------------------------------------


def _list_dir(directory: Path) -> list[Path]:
    """Return the asset files in a directory, sorted by name (dotfiles excluded)."""
    if not directory.is_dir():
        return []
    return sorted(
        p
        for p in directory.iterdir()
        if p.is_file()
        and not p.name.startswith(".")
        and p.suffix.lower() in _ALLOWED_EXTENSIONS
    )


def _safe_name(name: str) -> str | None:
    """Sanitize a filename to a bare, safe name, or ``None`` if nothing remains.

    Takes only the final path component (dropping any directory portion), strips
    disallowed characters, collapses whitespace, and bounds the stem length.
    Returns ``None`` when the result is empty, so callers reject it rather than
    writing an unnamed file.
    """
    # Drop any directory component a client may have sent (defence in depth on
    # top of the character strip below).
    base = Path(name.replace("\\", "/")).name
    stem = Path(base).stem
    suffix = Path(base).suffix
    stem = _ILLEGAL_NAME_CHARS.sub("", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    suffix = _ILLEGAL_NAME_CHARS.sub("", suffix)
    if not stem:
        return None
    if len(stem) > _MAX_NAME_STEM:
        stem = stem[:_MAX_NAME_STEM].rstrip(" .")
    return f"{stem}{suffix}"


def _unique_name(name: str) -> str:
    """Return ``name`` or ``stem-2.ext`` / ``stem-3.ext`` … so it is unused.

    Assumes the lock is held. Checks both directories so a user upload can never
    collide with a built-in or an existing user asset.
    """
    if not _name_taken(name):
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    counter = 2
    while True:
        candidate = f"{stem}-{counter}{suffix}"
        if not _name_taken(candidate):
            return candidate
        counter += 1


def _name_taken(name: str) -> bool:
    return (BUILTIN_DIR / name).is_file() or (USER_DIR / name).is_file()
