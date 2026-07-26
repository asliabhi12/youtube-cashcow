"""Storage-agnostic Profile Repository interface contract."""

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from app.models.profile import Profile, ProfileSummary


class IProfileRepository(ABC):
    """Encapsulates profile persistence without exposing storage technology."""

    @abstractmethod
    def list_all(self) -> Sequence[ProfileSummary]:
        """Return summaries of all profiles."""
        pass

    @abstractmethod
    def get_by_id(self, profile_id: str) -> Optional[Profile]:
        """Fetch a full profile entity by ID. Returns None if missing."""
        pass

    @abstractmethod
    def exists(self, profile_id: str) -> bool:
        """Check if a profile ID exists."""
        pass

    @abstractmethod
    def save(self, profile: Profile) -> Profile:
        """Persist a profile (create or update). Returns saved profile domain model."""
        pass

    @abstractmethod
    def delete(self, profile_id: str) -> bool:
        """Delete a profile entity by ID. Returns True if deleted, False if missing."""
        pass
