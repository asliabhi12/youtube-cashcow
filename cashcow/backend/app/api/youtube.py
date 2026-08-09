"""Minimal YouTube OAuth routes for the upload workflow."""

import logging

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.config import youtube_upload_config
from app.services.youtube_oauth import YouTubeOAuthError, authorization_url, connect_channel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/youtube", tags=["youtube"])


from urllib.parse import quote
from fastapi import Request


@router.get("/auth/start")
def start_youtube_auth(request: Request) -> RedirectResponse:
    """Redirect the user to Google consent for one upload account."""
    referer = request.headers.get("referer")
    return_url = referer if referer and referer.startswith("http") else None
    try:
        return RedirectResponse(
            authorization_url(return_url=return_url),
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
    except YouTubeOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/auth/callback")
def complete_youtube_auth(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Exchange Google's authorization code, fetch channel, save destination.

    Maintained for legacy redirect URI configurations.
    """
    fallback_url = youtube_upload_config.FRONTEND_DESTINATIONS_URL
    if error:
        logger.warning("[complete_youtube_auth] Google authorization error: %s", error)
        error_param = quote(f"Google authorization denied: {error}")
        return RedirectResponse(
            url=f"{fallback_url}?error={error_param}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if not code or not state:
        logger.warning("[complete_youtube_auth] Missing code or state parameter")
        error_param = quote("Invalid authorization response from Google")
        return RedirectResponse(
            url=f"{fallback_url}?error={error_param}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        dest, return_url = connect_channel(code, state)
        logger.info(
            "[complete_youtube_auth] connect_channel returned id=%s title=%s",
            dest.id,
            dest.name,
        )
        target_url = return_url or fallback_url
    except YouTubeOAuthError as exc:
        logger.warning("[complete_youtube_auth] YouTubeOAuthError: %s", exc)
        error_param = quote(str(exc))
        return RedirectResponse(
            url=f"{fallback_url}?error={error_param}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        logger.error("[complete_youtube_auth] unexpected error: %s", exc, exc_info=True)
        error_param = quote("Failed to connect YouTube channel due to an internal error")
        return RedirectResponse(
            url=f"{fallback_url}?error={error_param}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=target_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )
