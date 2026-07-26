"""Minimal YouTube OAuth routes for the upload workflow."""

import logging

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.config import youtube_upload_config
from app.services.youtube_oauth import YouTubeOAuthError, authorization_url, connect_channel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/auth/start")
def start_youtube_auth() -> RedirectResponse:
    """Redirect the user to Google consent for one upload account."""
    try:
        return RedirectResponse(authorization_url(), status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    except YouTubeOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/auth/callback")
def complete_youtube_auth(
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """Exchange Google's authorization code, fetch channel, save destination.

    Maintained for legacy redirect URI configurations.
    """
    try:
        dest = connect_channel(code, state)
        logger.info("[complete_youtube_auth] connect_channel returned id=%s title=%s", dest.id, dest.name)
    except YouTubeOAuthError as exc:
        logger.warning("[complete_youtube_auth] YouTubeOAuthError: %s", exc)
        error_url = f"{youtube_upload_config.FRONTEND_DESTINATIONS_URL}?error={exc}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        logger.error("[complete_youtube_auth] unexpected error: %s", exc, exc_info=True)
        raise

    return RedirectResponse(
        url=youtube_upload_config.FRONTEND_DESTINATIONS_URL,
        status_code=status.HTTP_303_SEE_OTHER,
    )
