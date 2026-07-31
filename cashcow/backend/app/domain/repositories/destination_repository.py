"""Destination & OAuth Repository interface contract."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence

from app.models.destination import Destination, DestinationStatus, DestinationTokenRecord


class IDestinationRepository(ABC):
    """Encapsulates destination channel persistence and OAuth tokens."""

    @abstractmethod
    def list_all(self) -> Sequence[Destination]:
        """Return all connected destinations."""
        pass

    @abstractmethod
    def get_by_id(self, destination_id: str) -> Optional[Destination]:
        """Fetch destination domain entity by ID."""
        pass

    @abstractmethod
    def get_token_record(self, destination_id: str) -> Optional[DestinationTokenRecord]:
        """Fetch OAuth credentials for a destination."""
        pass

    @abstractmethod
    def upsert_connected_channel(
        self,
        *,
        channel_title: str,
        channel_id: str,
        thumbnail: str,
        description: str,
        access_token: str,
        refresh_token: str,
        token_expires_at: Optional[datetime],
    ) -> Destination:
        """Persist or update connected YouTube channel credentials."""
        pass

    @abstractmethod
    def update_tokens(
        self,
        destination_id: str,
        *,
        access_token: str,
        token_expires_at: Optional[datetime],
        refresh_token: Optional[str] = None,
    ) -> Destination:
        """Update OAuth tokens for a destination."""
        pass

    @abstractmethod
    def mark_status(self, destination_id: str, status: DestinationStatus) -> None:
        """Update destination connection status."""
        pass

    @abstractmethod
    def delete(self, destination_id: str) -> bool:
        """Delete a destination entity."""
        pass

    @abstractmethod
    def store_oauth_state(self, state: str) -> None:
        """Store an OAuth CSRF state token."""
        pass

    @abstractmethod
    def consume_oauth_state(self, state: str) -> bool:
        """Atomically validate and consume an OAuth state token."""
        pass
