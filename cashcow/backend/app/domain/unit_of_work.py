"""Unit of Work interface for atomic transaction coordination."""

from abc import ABC, abstractmethod
from typing import Any, Callable

from app.domain.repositories.destination_repository import IDestinationRepository
from app.domain.repositories.job_repository import IJobRepository
from app.domain.repositories.memory_repository import IMemoryRepository
from app.domain.repositories.profile_repository import IProfileRepository


class IUnitOfWork(ABC):
    """Abstract Unit of Work context manager managing atomic multi-repository updates."""

    profiles: IProfileRepository
    destinations: IDestinationRepository
    jobs: IJobRepository
    memory: IMemoryRepository

    @abstractmethod
    def __enter__(self) -> "IUnitOfWork":
        pass

    @abstractmethod
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    @abstractmethod
    def commit(self) -> None:
        """Commit the atomic transaction."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Roll back all uncommitted changes in the transaction."""
        pass

    @abstractmethod
    def add_compensation_action(self, action: Callable[[], None]) -> None:
        """Register a compensation rollback action for out-of-band operations (file IO, external API)."""
        pass
