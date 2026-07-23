"""Destination CRUD routes plus OAuth connect flow."""

from fastapi import APIRouter, HTTPException, status

from app.core.config import youtube_upload_config
from app.models.destination import Destination
from app.services import destinations
from app.services.youtube_oauth import YouTubeOAuthError, authorization_url

router = APIRouter(prefix="/destinations", tags=["destinations"])


@router.get("", response_model=list[Destination])
def list_destinations() -> list[Destination]:
    return destinations.list_destinations()


@router.post("/connect")
def connect_destination() -> dict[str, str]:
    """Return the Google OAuth authorization URL to connect a YouTube channel."""
    try:
        auth_url = authorization_url()
    except YouTubeOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return {"authorization_url": auth_url}


@router.delete("/{destination_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_destination(destination_id: str) -> None:
    try:
        destinations.delete_destination(destination_id)
    except destinations.DestinationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found") from exc
