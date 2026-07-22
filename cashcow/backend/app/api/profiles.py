"""Creative-profile and application-settings routes.

Exposes CRUD over creative profiles (the reusable parameter bundles the Home
page selects and edits) plus the small application-settings store that remembers
the last-used profile. The backend owns the profile list; the frontend never
persists profiles itself.

Built-in profiles are read-only: a write or delete against one returns 403 so
the client falls back to "Save As" (duplicate). Validation errors from the
service map to 422, and unknown ids to 404.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.models.profile import Profile, ProfileInput, ProfileSummary
from app.services import app_settings, destinations, profiles
from app.services.presets import is_quality

router = APIRouter(tags=["profiles"])


def _validate_export_quality(data: ProfileInput) -> None:
    """Reject a profile whose export-quality default is not a known quality."""
    if data.export_quality is not None and not is_quality(data.export_quality):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown export quality: '{data.export_quality}'",
        )


def _validate_allowed_destinations(data: ProfileInput) -> None:
    for destination_id in data.allowed_destination_ids:
        if not destinations.destination_exists(destination_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown destination: '{destination_id}'",
            )


@router.get("/profiles", response_model=list[ProfileSummary])
def get_profiles() -> list[ProfileSummary]:
    """Return every profile as a summary, built-ins first then custom."""
    return profiles.list_profiles()


@router.get("/profiles/{profile_id}", response_model=Profile)
def get_profile(profile_id: str) -> Profile:
    """Return a single profile, or 404 if it does not exist."""
    profile = profiles.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.post("/profiles", response_model=Profile, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileInput) -> Profile:
    """Create a new custom profile and return it with its assigned id."""
    _validate_export_quality(payload)
    _validate_allowed_destinations(payload)
    return profiles.create_profile(payload)


@router.put("/profiles/{profile_id}", response_model=Profile)
def update_profile(profile_id: str, payload: ProfileInput) -> Profile:
    """Overwrite a custom profile.

    Returns 403 for a built-in (the client should "Save As" instead) and 404 if
    the custom profile does not exist.
    """
    _validate_export_quality(payload)
    _validate_allowed_destinations(payload)
    try:
        return profiles.update_profile(profile_id, payload)
    except profiles.ProfileReadOnlyError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except profiles.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: str) -> None:
    """Delete a custom profile.

    Returns 403 for a built-in and 404 if the custom profile does not exist.
    """
    try:
        profiles.delete_profile(profile_id)
    except profiles.ProfileReadOnlyError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except profiles.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


class DuplicateProfileRequest(BaseModel):
    """Optional body for POST /profiles/{id}/duplicate."""

    label: str | None = None


@router.post(
    "/profiles/{profile_id}/duplicate",
    response_model=Profile,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_profile(
    profile_id: str, payload: DuplicateProfileRequest | None = None
) -> Profile:
    """Copy any profile (built-in or custom) into a new editable custom profile."""
    label = payload.label if payload is not None else None
    try:
        return profiles.duplicate_profile(profile_id, label=label)
    except profiles.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/settings", response_model=app_settings.AppSettings)
def get_settings() -> app_settings.AppSettings:
    """Return application settings.

    ``last_profile`` is reported as ``None`` when it no longer resolves to an
    existing profile, so a stale pointer (e.g. a since-deleted custom profile)
    never breaks the Home page.
    """
    settings = app_settings.get_app_settings()
    if settings.last_profile is not None and not profiles.profile_exists(settings.last_profile):
        settings.last_profile = None
    return settings


class UpdateSettingsRequest(BaseModel):
    """Body for PUT /settings."""

    last_profile: str | None = None


@router.put("/settings", response_model=app_settings.AppSettings)
def update_settings(payload: UpdateSettingsRequest) -> app_settings.AppSettings:
    """Update application settings.

    Rejects a ``last_profile`` that does not name a known profile with 422. A
    ``null`` value clears the pointer.
    """
    if payload.last_profile is not None and not profiles.profile_exists(payload.last_profile):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown profile: '{payload.last_profile}'",
        )
    return app_settings.set_last_profile(payload.last_profile)
