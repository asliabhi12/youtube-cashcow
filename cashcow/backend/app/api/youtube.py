"""Minimal YouTube OAuth routes for the upload workflow."""

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.services.youtube_oauth import YouTubeOAuthError, authorization_url, exchange_code

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
) -> dict[str, str | bool]:
    """Exchange Google's authorization code and store the refresh token locally."""
    try:
        tokens = exchange_code(code, state)
    except YouTubeOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {
        "connected": True,
        "refresh_token_stored": tokens.refresh_token is not None,
        "message": "YouTube account connected. You can now run upload jobs.",
    }
