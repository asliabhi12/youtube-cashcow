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

from pydantic import BaseModel, Field
from fastapi import Request


class ConnectDestinationInput(BaseModel):
    return_url: str | None = Field(default=None, alias="return_url")


@router.post("/connect")
def connect_destination(
    request: Request,
    payload: ConnectDestinationInput | None = None,
) -> dict[str, str]:
    """Return the Google OAuth authorization URL to connect a YouTube channel."""
    return_url = payload.return_url if payload and payload.return_url else None
    if not return_url:
        referer = request.headers.get("referer")
        if referer and referer.startswith("http"):
            return_url = referer

    try:
        auth_url = authorization_url(return_url=return_url)
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
