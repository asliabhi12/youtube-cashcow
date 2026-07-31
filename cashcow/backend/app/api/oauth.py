"""Google OAuth callback route for YouTube destination connection."""

import logging

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.config import youtube_upload_config
from app.services.youtube_oauth import YouTubeOAuthError, connect_channel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.get("/google/callback")
def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """Exchange Google's authorization code, fetch channel, save destination.

    On success the user is redirected to the frontend destinations page.
    On error they are redirected with a query param ``error`` so the frontend
    can display a meaningful message.
    """
    try:
        dest = connect_channel(code, state)
        logger.info("[google_oauth_callback] connect_channel returned id=%s title=%s", dest.id, dest.name)
    except YouTubeOAuthError as exc:
        logger.warning("[google_oauth_callback] YouTubeOAuthError: %s", exc)
        error_url = f"{youtube_upload_config.FRONTEND_DESTINATIONS_URL}?error={exc}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        logger.error("[google_oauth_callback] unexpected error: %s", exc, exc_info=True)
        raise

    return RedirectResponse(
        url=youtube_upload_config.FRONTEND_DESTINATIONS_URL,
        status_code=status.HTTP_303_SEE_OTHER,
    )
