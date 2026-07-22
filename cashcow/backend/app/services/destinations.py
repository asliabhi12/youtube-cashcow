"""In-memory destination catalogue.

The app does not have persistent backend storage for destinations yet, so this
module mirrors the existing in-memory job store while exposing a stable service
boundary for future database-backed CRUD.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.models.destination import Destination, DestinationInput

_lock = Lock()
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(value: str) -> str:
    slug = _SLUG_STRIP.sub("-", value.lower()).strip("-")
    return slug or "destination"


def _seed_destination(
    *,
    name: str,
    channel_id: str,
    description: str,
    thumbnail: str,
) -> Destination:
    stamp = _now()
    return Destination(
        id=_slugify(name),
        name=name,
        platform="youtube",
        channelId=channel_id,
        thumbnail=thumbnail,
        description=description,
        connectionStatus="connected",
        oauthStatus="authorized",
        defaultVisibility="private",
        defaultPlaylist="",
        defaultLanguage="en",
        createdAt=stamp,
        updatedAt=stamp,
    )


_destinations: dict[str, Destination] = {
    item.id: item
    for item in [
        _seed_destination(
            name="Ramayani Rides",
            channel_id="UC-ramayani-rides",
            description="Primary long-form and Shorts destination.",
            thumbnail="RR",
        ),
        _seed_destination(
            name="Bhakti Aastha",
            channel_id="UC-bhakti-aastha",
            description="Devotional clips and metadata-ready exports.",
            thumbnail="BA",
        ),
        _seed_destination(
            name="Chotu TV",
            channel_id="UC-chotu-tv",
            description="Family-friendly short video channel.",
            thumbnail="CT",
        ),
    ]
}


class DestinationNotFoundError(Exception):
    """Raised when a destination id does not exist."""


def list_destinations() -> list[Destination]:
    """Return destinations ordered by creation time."""
    with _lock:
        return sorted(_destinations.values(), key=lambda item: item.created_at)


def get_destination(destination_id: str) -> Destination | None:
    with _lock:
        return _destinations.get(destination_id)


def destination_exists(destination_id: str) -> bool:
    return get_destination(destination_id) is not None


def default_destination_ids() -> list[str]:
    """Default publish targets for legacy clients that do not send destinations."""
    with _lock:
        connected = [
            destination.id
            for destination in sorted(_destinations.values(), key=lambda item: item.created_at)
            if destination.connection_status == "connected"
        ]
        return connected[:1]


def create_destination(data: DestinationInput) -> Destination:
    with _lock:
        base = _slugify(data.name)
        destination_id = base
        suffix = 2
        while destination_id in _destinations:
            destination_id = f"{base}-{suffix}"
            suffix += 1
        stamp = _now()
        destination = Destination(
            id=destination_id,
            createdAt=stamp,
            updatedAt=stamp,
            **data.model_dump(by_alias=True),
        )
        _destinations[destination.id] = destination
        return destination


def update_destination(destination_id: str, data: DestinationInput) -> Destination:
    with _lock:
        existing = _destinations.get(destination_id)
        if existing is None:
            raise DestinationNotFoundError(destination_id)
        destination = Destination(
            id=destination_id,
            createdAt=existing.created_at,
            updatedAt=_now(),
            **data.model_dump(by_alias=True),
        )
        _destinations[destination_id] = destination
        return destination


def delete_destination(destination_id: str) -> None:
    with _lock:
        if _destinations.pop(destination_id, None) is None:
            raise DestinationNotFoundError(destination_id)
