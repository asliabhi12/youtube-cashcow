"""Profile Repository implementation hiding filesystem/YAML storage mechanics."""

import copy
import logging
import os
import re
import tempfile
from pathlib import Path
from threading import Lock
from typing import Optional, Sequence

import yaml
from pydantic import ValidationError

from app.core.config import AppConfig, get_app_config
from app.domain.repositories.profile_repository import IProfileRepository
from app.models.profile import Profile, ProfileInput, ProfileSummary

logger = logging.getLogger(__name__)

CUSTOM_ID = "custom"
_CUSTOM_PROFILE = Profile(
    id=CUSTOM_ID,
    builtin=True,
    label="Custom",
    description="No creative modifications — runs the base pipeline as-is.",
)

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


class YAMLProfileRepository(IProfileRepository):
    """Concrete profile repository implementation operating on pure domain models."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config or get_app_config()
        self._lock = Lock()

    @property
    def builtin_dir(self) -> Path:
        return self._config.storage.builtin_profiles_dir

    @property
    def custom_dir(self) -> Path:
        return self._config.storage.custom_profiles_dir

    def list_all(self) -> Sequence[ProfileSummary]:
        summaries: list[ProfileSummary] = [self._summary(_CUSTOM_PROFILE)]

        for profile in self._load_dir(self.builtin_dir, builtin=True):
            summaries.append(self._summary(profile))

        builtin_ids = {s.id for s in summaries}
        for profile in self._load_dir(self.custom_dir, builtin=False):
            if profile.id in builtin_ids:
                logger.warning("Custom profile '%s' shadows a built-in id; skipping", profile.id)
                continue
            summaries.append(self._summary(profile))

        return summaries

    def get_by_id(self, profile_id: str) -> Optional[Profile]:
        if profile_id == CUSTOM_ID:
            return _CUSTOM_PROFILE

        builtin_path = self._builtin_path(profile_id)
        if builtin_path is not None:
            return self._load_file(builtin_path, builtin=True)

        custom_path = self._custom_path(profile_id)
        if custom_path is not None:
            return self._load_file(custom_path, builtin=False)

        return None

    def exists(self, profile_id: str) -> bool:
        return self.get_by_id(profile_id) is not None

    def save(self, profile: Profile) -> Profile:
        with self._lock:
            self.custom_dir.mkdir(parents=True, exist_ok=True)
            payload = profile.model_dump(exclude_none=True, exclude={"id", "builtin", "warnings"})
            text = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, allow_unicode=True)

            target = self.custom_dir / f"{profile.id}.yaml"
            fd, tmp_path = tempfile.mkstemp(dir=str(self.custom_dir), suffix=".tmp")
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

            return copy.deepcopy(profile)

    def delete(self, profile_id: str) -> bool:
        with self._lock:
            path = self._custom_path(profile_id)
            if path is None:
                return False
            path.unlink()
            return True

    def _load_dir(self, directory: Path, *, builtin: bool) -> list[Profile]:
        if not directory.is_dir():
            return []
        profiles: list[Profile] = []
        for path in sorted(directory.glob("*.yaml")):
            profile = self._load_file(path, builtin=builtin)
            if profile is not None:
                profiles.append(profile)
        return profiles

    def _load_file(self, path: Path, *, builtin: bool) -> Optional[Profile]:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            data = ProfileInput.model_validate(raw)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            logger.warning("Skipping unreadable profile '%s': %s", path.name, exc)
            return None
        fields = data.model_dump(exclude={"id", "builtin", "warnings"})
        return Profile(id=path.stem, builtin=builtin, **fields)

    def _builtin_path(self, profile_id: str) -> Optional[Path]:
        path = self.builtin_dir / f"{profile_id}.yaml"
        return path if path.is_file() else None

    def _custom_path(self, profile_id: str) -> Optional[Path]:
        path = self.custom_dir / f"{profile_id}.yaml"
        return path if path.is_file() else None

    def _summary(self, profile: Profile) -> ProfileSummary:
        return ProfileSummary(
            id=profile.id,
            label=profile.label,
            description=profile.description,
            builtin=profile.builtin,
        )
