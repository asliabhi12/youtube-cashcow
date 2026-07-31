"""Domain Event Bus for decoupling CashCow services."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from threading import Lock
from typing import Any, Callable, Dict, List, Type

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ProfileSaved(DomainEvent):
    profile_id: str
    is_builtin: bool


@dataclass(frozen=True)
class ProfileDeleted(DomainEvent):
    profile_id: str


@dataclass(frozen=True)
class DestinationConnected(DomainEvent):
    destination_id: str
    channel_id: str
    channel_title: str


@dataclass(frozen=True)
class DestinationDisconnected(DomainEvent):
    destination_id: str


@dataclass(frozen=True)
class JobStatusChanged(DomainEvent):
    job_id: str
    status: str
    error: str | None = None


@dataclass(frozen=True)
class VideoMetadataGenerated(DomainEvent):
    job_id: str
    title: str


@dataclass(frozen=True)
class UploadCompleted(DomainEvent):
    job_id: str
    destination_id: str
    video_id: str | None = None


EventHandler = Callable[[DomainEvent], None]


class EventBus:
    """In-memory thread-safe event bus for domain events."""

    def __init__(self) -> None:
        self._handlers: Dict[Type[DomainEvent], List[EventHandler]] = {}
        self._lock = Lock()

    def subscribe(self, event_type: Type[DomainEvent], handler: EventHandler) -> None:
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        event_type = type(event)
        handlers: List[EventHandler] = []
        with self._lock:
            if event_type in self._handlers:
                handlers = list(self._handlers[event_type])

        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error("Error executing handler %s for event %s: %s", handler, event, exc)


_global_event_bus = EventBus()


def get_event_bus() -> EventBus:
    return _global_event_bus
