"""Creative-profile storage and management.

Profiles are YAML files on disk, split into two directories at the repository
root:

* ``profiles/*.yaml`` — **built-in** profiles bundled with the app. Read-only:
  they can be duplicated ("Save As") but never overwritten or deleted.
* ``profiles/custom/*.yaml`` — **user** profiles. Fully editable and deletable.

A profile's id is its filename stem. Each file stores only editable creative
parameters (``resize`` / ``audio`` / ``color`` / ``overlay``), metadata-generation
guidance (``metadata_prompt``), display metadata (``label`` / ``description``),
and an optional ``export_quality`` default — never workflow steps. This module is
the single source of truth for the profile list; the workflow adapter consumes
:func:`resolve_config` to inject a profile's parameters into the fixed pipeline,
exactly where the old static ``presets.preset_config`` was used.

Writes validate through the pydantic models first, then serialize atomically
(temp file + ``os.replace``) under a module lock, so a concurrent read never
observes a partial file and an invalid profile is never written.
"""

from __future__ import annotations

import copy
import logging
import os
import re
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any

import yaml
from pydantic import ValidationError

from app.models.profile import Profile, ProfileInput, ProfileSummary

logger = logging.getLogger(__name__)

# Repository root, resolved like ``workflow.py`` / ``app_settings.py``:
# services → app → backend → cashcow → repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
BUILTIN_DIR = _PROJECT_ROOT / "profiles"
CUSTOM_DIR = BUILTIN_DIR / "custom"

# Synthetic id kept for back-compat with the retired ``custom`` editing preset:
# it names "no creative modifications" and always runs the bare pipeline. It has
# no file on disk and cannot be edited or deleted.
CUSTOM_ID = "custom"
_CUSTOM_PROFILE = Profile(
    id=CUSTOM_ID,
    builtin=True,
    label="Custom",
    description="No creative modifications — runs the base pipeline as-is.",
)

_lock = Lock()


class ProfileError(Exception):
    """Base class for profile-management errors."""


class ProfileNotFoundError(ProfileError):
    """Raised when a profile id does not resolve to a known profile."""


class ProfileReadOnlyError(ProfileError):
    """Raised on an attempt to modify or delete a built-in profile."""


class ProfileValidationError(ProfileError):
    """Raised when profile data fails validation."""


# --- Reads -----------------------------------------------------------------


def list_profiles() -> list[ProfileSummary]:
    """Return every profile as a summary, built-ins first then custom.

    A custom file that fails to load (corrupt YAML, invalid shape, or a stem
    that collides with a built-in) is skipped with a warning rather than
    breaking the whole list.
    """
    summaries: list[ProfileSummary] = [_summary(_CUSTOM_PROFILE)]

    for profile in _load_dir(BUILTIN_DIR, builtin=True):
        summaries.append(_summary(profile))

    builtin_ids = {s.id for s in summaries}
    for profile in _load_dir(CUSTOM_DIR, builtin=False):
        if profile.id in builtin_ids:
            logger.warning(
                "Custom profile '%s' shadows a built-in id; skipping", profile.id
            )
            continue
        summaries.append(_summary(profile))

    return summaries


def get_profile(profile_id: str) -> Profile | None:
    """Return a full profile by id, or ``None`` if it does not exist.

    Built-ins take precedence over a custom file of the same id.
    """
    if profile_id == CUSTOM_ID:
        return _CUSTOM_PROFILE

    builtin_path = _builtin_path(profile_id)
    if builtin_path is not None:
        return _load_file(builtin_path, builtin=True)

    custom_path = _custom_path(profile_id)
    if custom_path is not None:
        return _load_file(custom_path, builtin=False)

    return None


def profile_exists(profile_id: str) -> bool:
    """Whether ``profile_id`` names a known profile."""
    return get_profile(profile_id) is not None


def is_builtin(profile_id: str) -> bool:
    """Whether ``profile_id`` names a built-in (read-only) profile."""
    return profile_id == CUSTOM_ID or _builtin_path(profile_id) is not None


def resolve_config(profile_id: str) -> dict[str, Any]:
    """Return a profile's creative config in the shape the adapter injects.

    The result is a fresh dict with only the creative keys present on the
    profile (``resize`` / ``audio`` / ``color`` / ``overlay``), each mirroring
    the option shape the corresponding engine step accepts. A missing key means
    that step is skipped — identical to the old ``presets.preset_config``
    contract. The synthetic ``custom`` id (or any unknown id) yields an empty
    config, i.e. the bare download → encode → export pipeline.
    """
    profile = get_profile(profile_id)
    if profile is None:
        return {}

    config: dict[str, Any] = {}
    if profile.resize is not None:
        config["resize"] = profile.resize.model_dump(exclude_none=True)
    if profile.audio is not None:
        config["audio"] = {
            "effects": [item.model_dump(exclude_none=True) for item in profile.audio.effects]
        }
    if profile.color is not None:
        config["color"] = profile.color.model_dump()
    if profile.overlay is not None:
        config["overlay"] = profile.overlay.model_dump(exclude_none=True)
    # Deep copy so callers can freely mutate (e.g. inject the resolved overlay
    # path) without touching anything cached.
    return copy.deepcopy(config)


# --- Writes ----------------------------------------------------------------


def create_profile(data: ProfileInput) -> Profile:
    """Create a new custom profile from ``data`` and return it.

    The id is derived by slugifying the label and made unique across *both*
    directories, so a new profile never shadows a built-in or an existing custom
    one.
    """
    with _lock:
        profile_id = _unique_id(_slugify(data.label))
        return _write_custom(profile_id, data)


def update_profile(profile_id: str, data: ProfileInput) -> Profile:
    """Overwrite an existing custom profile.

    Raises :class:`ProfileReadOnlyError` for a built-in and
    :class:`ProfileNotFoundError` if the custom profile does not exist.
    """
    with _lock:
        if is_builtin(profile_id):
            raise ProfileReadOnlyError(f"Profile '{profile_id}' is read-only")
        if _custom_path(profile_id) is None:
            raise ProfileNotFoundError(f"Profile '{profile_id}' not found")
        return _write_custom(profile_id, data)


def delete_profile(profile_id: str) -> None:
    """Delete a custom profile.

    Raises :class:`ProfileReadOnlyError` for a built-in and
    :class:`ProfileNotFoundError` if the custom profile does not exist.
    """
    with _lock:
        if is_builtin(profile_id):
            raise ProfileReadOnlyError(f"Profile '{profile_id}' is read-only")
        path = _custom_path(profile_id)
        if path is None:
            raise ProfileNotFoundError(f"Profile '{profile_id}' not found")
        path.unlink()


def duplicate_profile(profile_id: str, *, label: str | None = None) -> Profile:
    """Copy any profile into a new custom profile ("Save As").

    The copy takes ``label`` when given, otherwise the source label suffixed
    with " (copy)". Raises :class:`ProfileNotFoundError` if the source is
    unknown.
    """
    with _lock:
        source = get_profile(profile_id)
        if source is None:
            raise ProfileNotFoundError(f"Profile '{profile_id}' not found")
        new_label = label or f"{source.label} (copy)"
        # Carry over every editable field, only swapping the label.
        data = ProfileInput(**{**_input_fields(source), "label": new_label})
        new_id = _unique_id(_slugify(new_label))
        return _write_custom(new_id, data)


# --- Internals -------------------------------------------------------------


def _write_custom(profile_id: str, data: ProfileInput) -> Profile:
    """Serialize ``data`` to ``CUSTOM_DIR/{id}.yaml`` atomically. Assumes lock held."""
    CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump(exclude_none=True)
    text = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, allow_unicode=True)

    target = CUSTOM_DIR / f"{profile_id}.yaml"
    fd, tmp_path = tempfile.mkstemp(dir=str(CUSTOM_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_path, target)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return Profile(id=profile_id, builtin=False, **data.model_dump())


def _input_fields(profile: Profile) -> dict[str, Any]:
    """Extract the editable (ProfileInput) fields from a full Profile."""
    return {name: getattr(profile, name) for name in ProfileInput.model_fields}


def _load_dir(directory: Path, *, builtin: bool) -> list[Profile]:
    """Load all ``*.yaml`` profiles in a directory, sorted by id.

    A file that fails to load is skipped with a warning so one bad file does not
    hide the rest.
    """
    if not directory.is_dir():
        return []
    profiles: list[Profile] = []
    for path in sorted(directory.glob("*.yaml")):
        profile = _load_file(path, builtin=builtin)
        if profile is not None:
            profiles.append(profile)
    return profiles


def _load_file(path: Path, *, builtin: bool) -> Profile | None:
    """Parse and validate a single profile file. Returns ``None`` on failure."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data = ProfileInput.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        logger.warning("Skipping unreadable profile '%s': %s", path.name, exc)
        return None
    return Profile(id=path.stem, builtin=builtin, **data.model_dump())


def _builtin_path(profile_id: str) -> Path | None:
    """Path to a built-in profile file if it exists, else ``None``."""
    path = BUILTIN_DIR / f"{profile_id}.yaml"
    return path if path.is_file() else None


def _custom_path(profile_id: str) -> Path | None:
    """Path to a custom profile file if it exists, else ``None``."""
    path = CUSTOM_DIR / f"{profile_id}.yaml"
    return path if path.is_file() else None


def _summary(profile: Profile) -> ProfileSummary:
    return ProfileSummary(
        id=profile.id,
        label=profile.label,
        description=profile.description,
        builtin=profile.builtin,
    )


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slugify(label: str) -> str:
    """Turn a label into a filesystem-safe id stem.

    Lowercases, replaces any run of non-alphanumerics with a single hyphen, and
    trims stray hyphens. Falls back to ``profile`` if nothing usable remains
    (e.g. a label of only punctuation), so a valid id is always produced.
    """
    slug = _SLUG_STRIP.sub("-", label.lower()).strip("-")
    return slug or "profile"


def _unique_id(base: str) -> str:
    """Return ``base`` or ``base-2`` / ``base-3`` … so the id is unused anywhere.

    Assumes the lock is held. Checks both directories and the synthetic
    ``custom`` id, so a custom profile can never collide with a built-in.
    """
    candidate = base
    suffix = 2
    while _id_taken(candidate):
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _id_taken(profile_id: str) -> bool:
    return (
        profile_id == CUSTOM_ID
        or _builtin_path(profile_id) is not None
        or _custom_path(profile_id) is not None
    )
