"""Creative-profile and application-settings routes.

Exposes CRUD over creative profiles (the reusable parameter bundles the Home
page selects and edits) plus the small application-settings store that remembers
the last-used profile. The backend owns the profile list; the frontend never
persists profiles itself.

Built-in profiles are read-only: a write or delete against one returns 403 so
the client falls back to "Save As" (duplicate). Validation errors from the
service map to 422, and unknown ids to 404.
"""

import logging
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.models.profile import Profile, ProfileInput, ProfileSummary
from app.services import app_settings, destinations, profiles
from app.services.presets import is_quality

logger = logging.getLogger(__name__)
router = APIRouter(tags=["profiles"])


def _log_profile_request(request: Request | None, payload: ProfileInput, action: str) -> None:
    headers = dict(request.headers) if request else {}
    model_fields = list(ProfileInput.model_fields.keys())
    dump = payload.model_dump(by_alias=True)
    logger.info(
        "[%s Profile] Request Headers: %s", action, headers
    )
    logger.info(
        "[%s Profile] Parsed Request Body: %s", action, dump
    )
    logger.info(
        "[%s Profile] Pydantic Model Fields: %s", action, model_fields
    )
    logger.info(
        "[%s Profile] Alias Mapping: metadataPrompt -> metadata_prompt, exportQuality -> export_quality, allowedDestinationIds -> allowed_destination_ids",
        action,
    )


def _validate_export_quality(data: ProfileInput) -> None:
    """Reject a profile whose export-quality default is not a known quality."""
    if data.export_quality is not None and not is_quality(data.export_quality):
        logger.error("[Profile Validation] Unknown export quality: '%s'", data.export_quality)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown export quality: '{data.export_quality}'",
        )


def _validate_allowed_destinations(data: ProfileInput, profile_id: str = "custom") -> list[str]:
    """Migrate allowed_destination_ids to valid existing OAuth destinations and return warnings."""
    return profiles.migrate_input_destinations(data, profile_id=profile_id)


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
    logger.info("[GET Profile] Loaded stored profile: %s", profile.model_dump(by_alias=True))
    return profile


@router.post("/profiles", response_model=Profile, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileInput, request: Request = None) -> Profile:
    """Create a new custom profile and return it with its assigned id."""
    _log_profile_request(request, payload, "POST")
    _validate_export_quality(payload)
    warnings = _validate_allowed_destinations(payload, profile_id=payload.label or "new_profile")
    created = profiles.create_profile(payload)
    if warnings:
        for w in warnings:
            if w not in created.warnings:
                created.warnings.append(w)
    return created


@router.put("/profiles/{profile_id}", response_model=Profile)
def update_profile(profile_id: str, payload: ProfileInput, request: Request = None) -> Profile:
    """Overwrite a custom profile.

    Returns 403 for a built-in (the client should "Save As" instead) and 404 if
    the custom profile does not exist.
    """
    _log_profile_request(request, payload, f"PUT {profile_id}")
    _validate_export_quality(payload)
    warnings = _validate_allowed_destinations(payload, profile_id=profile_id)
    try:
        updated = profiles.update_profile(profile_id, payload)
        if warnings:
            for w in warnings:
                if w not in updated.warnings:
                    updated.warnings.append(w)
        return updated
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
