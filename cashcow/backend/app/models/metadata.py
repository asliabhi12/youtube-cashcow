"""Schemas for generated, YouTube-ready video metadata."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TITLE_MAX_LENGTH = 100
DESCRIPTION_MAX_LENGTH = 5_000
TAGS_MAX_LENGTH = 500
HASHTAGS_MAX_COUNT = 15
THUMBNAIL_PROMPT_MAX_LENGTH = 1_000


def _normalize_hashtag(value: str) -> str:
    """Return a hashtag in the form YouTube accepts."""
    value = value.strip()
    return value if value.startswith("#") else f"#{value}"


def _normalize_list(values: list[str]) -> list[str]:
    """Strip and de-duplicate list values while preserving user order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item:
            raise ValueError("metadata list items must not be empty")
        key = item.casefold()
        if key not in seen:
            normalized.append(item)
            seen.add(key)
    return normalized


def _normalize_hashtags(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _normalize_hashtag(value)
        if item == "#":
            raise ValueError("hashtags must contain text after '#'")
        key = item.casefold()
        if key not in seen:
            normalized.append(item)
            seen.add(key)
    return normalized


class MetadataFields(BaseModel):
    """Editable metadata fields shared by create, update, and response models."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    description: str = Field(default="", max_length=DESCRIPTION_MAX_LENGTH)
    tags: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list, max_length=HASHTAGS_MAX_COUNT)
    category: str = Field(default="", max_length=100)
    thumbnail_prompt: str = Field(default="", max_length=THUMBNAIL_PROMPT_MAX_LENGTH)

    @field_validator("title")
    @classmethod
    def _title_is_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("tags")
    @classmethod
    def _tags_are_normalized(cls, values: list[str]) -> list[str]:
        return _normalize_list(values)

    @field_validator("hashtags")
    @classmethod
    def _hashtags_are_valid(cls, values: list[str]) -> list[str]:
        return _normalize_hashtags(values)

    @model_validator(mode="after")
    def _tags_fit_youtube_limit(self) -> "MetadataFields":
        # The YouTube API limit is measured over the comma-separated tag value.
        if len(",".join(tag.strip() for tag in self.tags)) > TAGS_MAX_LENGTH:
            raise ValueError(f"tags must be at most {TAGS_MAX_LENGTH} characters total")
        return self


class MetadataCreate(BaseModel):
    """Optional overrides supplied while generating metadata."""

    model_config = ConfigDict(extra="forbid")

    title_seed: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    tags: list[str] | None = None
    hashtags: list[str] | None = Field(default=None, max_length=HASHTAGS_MAX_COUNT)
    category: str | None = Field(default=None, max_length=100)
    thumbnail_prompt: str | None = Field(default=None, max_length=THUMBNAIL_PROMPT_MAX_LENGTH)

    @field_validator("title_seed", "title")
    @classmethod
    def _title_is_nonblank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("tags")
    @classmethod
    def _tags_are_normalized(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _normalize_list(values)

    @field_validator("hashtags")
    @classmethod
    def _hashtags_are_valid(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _normalize_hashtags(values)

    @model_validator(mode="after")
    def _tags_fit_youtube_limit(self) -> "MetadataCreate":
        if self.tags is not None and len(",".join(tag.strip() for tag in self.tags)) > TAGS_MAX_LENGTH:
            raise ValueError(f"tags must be at most {TAGS_MAX_LENGTH} characters total")
        return self


class MetadataUpdate(MetadataCreate):
    """Partial metadata edit. Omitted fields retain their existing values."""


class MetadataResponse(BaseModel):
    """Strict AI-provider response: only generated YouTube metadata fields."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX_LENGTH)
    tags: list[str] = Field(default_factory=list)

    @field_validator("title", "description")
    @classmethod
    def _text_is_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("metadata text fields must not be blank")
        return value

    @field_validator("tags")
    @classmethod
    def _tags_are_normalized(cls, values: list[str]) -> list[str]:
        return _normalize_list(values)

    @model_validator(mode="after")
    def _tags_fit_youtube_limit(self) -> "MetadataResponse":
        if len(",".join(tag.strip() for tag in self.tags)) > TAGS_MAX_LENGTH:
            raise ValueError(f"tags must be at most {TAGS_MAX_LENGTH} characters total")
        return self


class VideoMetadata(MetadataFields):
    """Metadata stored for one processing job."""

    job_id: str
    generated_at: datetime
    provider: str
    model: str
    editable: bool = True
