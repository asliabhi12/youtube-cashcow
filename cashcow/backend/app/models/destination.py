"""Destination management schemas.

A destination is an external publishing target. The initial implementation uses
an in-memory catalogue seeded with YouTube channels, but the model is platform
neutral so future providers can be added without reshaping profiles or jobs.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DestinationPlatform = Literal[
    "youtube",
    "tiktok",
    "instagram",
    "facebook",
    "linkedin",
    "x",
]
DestinationStatus = Literal["connected", "disconnected", "expired", "error"]
DestinationOAuthStatus = Literal["not_configured", "authorized", "expired", "error"]
JobDestinationStatus = Literal["queued", "uploading", "success", "failed", "skipped"]


class DestinationInput(BaseModel):
    """Editable destination fields."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    platform: DestinationPlatform
    channel_id: str = Field(default="", alias="channelId")
    thumbnail: str = ""
    description: str = ""
    connection_status: DestinationStatus = Field(default="disconnected", alias="connectionStatus")
    oauth_status: DestinationOAuthStatus = Field(default="not_configured", alias="oauthStatus")
    default_visibility: str = Field(default="private", alias="defaultVisibility")
    default_playlist: str = Field(default="", alias="defaultPlaylist")
    default_language: str = Field(default="en", alias="defaultLanguage")


class Destination(DestinationInput):
    """A stored publishing target."""

    id: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class JobDestination(BaseModel):
    """A destination snapshot attached to a job with independent publish status."""

    id: str
    destination_id: str = Field(alias="destinationId")
    name: str
    platform: DestinationPlatform
    status: JobDestinationStatus = "queued"
    video_id: str | None = Field(default=None, alias="videoId")
    video_url: str | None = Field(default=None, alias="videoUrl")
    error: str | None = None
    updated_at: datetime = Field(alias="updatedAt")

