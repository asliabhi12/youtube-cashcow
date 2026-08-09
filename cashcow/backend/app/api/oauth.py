"""Google OAuth callback route for YouTube destination connection."""

import logging

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.config import youtube_upload_config
from app.services.youtube_oauth import YouTubeOAuthError, connect_channel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])


from urllib.parse import quote

@router.get("/google/callback")
def google_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Exchange Google's authorization code, fetch channel, save destination.

    On success the user is redirected to the frontend destinations page.
    On error they are redirected with a query param ``error`` so the frontend
    can display a meaningful message.
    """
    fallback_url = youtube_upload_config.FRONTEND_DESTINATIONS_URL
    if error:
        logger.warning("[google_oauth_callback] Google authorization error: %s", error)
        error_param = quote(f"Google authorization denied: {error}")
        return RedirectResponse(
            url=f"{fallback_url}?error={error_param}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if not code or not state:
        logger.warning("[google_oauth_callback] Missing code or state parameter")
        error_param = quote("Invalid authorization response from Google")
        return RedirectResponse(
            url=f"{fallback_url}?error={error_param}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        dest, return_url = connect_channel(code, state)
        logger.info(
            "[google_oauth_callback] connect_channel returned id=%s title=%s",
            dest.id,
            dest.name,
        )
        target_url = return_url or fallback_url
    except YouTubeOAuthError as exc:
        logger.warning("[google_oauth_callback] YouTubeOAuthError: %s", exc)
        error_param = quote(str(exc))
        return RedirectResponse(
            url=f"{fallback_url}?error={error_param}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        logger.error("[google_oauth_callback] unexpected error: %s", exc, exc_info=True)
        error_param = quote("Failed to connect YouTube channel due to an internal error")
        return RedirectResponse(
            url=f"{fallback_url}?error={error_param}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=target_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )
