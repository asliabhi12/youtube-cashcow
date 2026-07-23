"""Destination management schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DestinationPlatform = Literal["youtube"]
DestinationStatus = Literal["connected", "needs_reconnection", "disconnected", "error"]
JobDestinationStatus = Literal["queued", "uploading", "success", "failed", "skipped"]
PrivacyStatus = Literal["private", "unlisted", "public"]


class UploadSettings(BaseModel):
    """Per-job/per-upload YouTube metadata and visibility settings."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    privacy: PrivacyStatus = "private"
    playlist: str = ""
    thumbnail: str = ""
    language: str = "en"
    category: str = "22"
    made_for_kids: bool = Field(default=False, alias="madeForKids")


class Destination(BaseModel):
    """A connected YouTube channel, without OAuth secrets."""

    id: str
    name: str
    channel_title: str = Field(alias="channelTitle")
    channel_id: str = Field(alias="channelId")
    thumbnail: str
    description: str = ""
    platform: DestinationPlatform = "youtube"
    connection_status: DestinationStatus = Field(alias="connectionStatus")
    token_expires_at: datetime | None = Field(default=None, alias="tokenExpiresAt")
    last_synced_at: datetime | None = Field(default=None, alias="lastSyncedAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class JobDestination(BaseModel):
    """A destination snapshot attached to a job with independent publish status."""

    id: str
    destination_id: str = Field(alias="destinationId")
    name: str
    platform: DestinationPlatform
    status: JobDestinationStatus = "queued"
    progress: int = Field(default=0, ge=0, le=100)
    video_id: str | None = Field(default=None, alias="videoId")
    video_url: str | None = Field(default=None, alias="videoUrl")
    error: str | None = None
    upload_settings: UploadSettings = Field(default_factory=UploadSettings, alias="uploadSettings")
    updated_at: datetime = Field(alias="updatedAt")


class DestinationTokenRecord(BaseModel):
    """Server-side destination record including OAuth credentials."""

    destination: Destination
    access_token: str
    refresh_token: str
