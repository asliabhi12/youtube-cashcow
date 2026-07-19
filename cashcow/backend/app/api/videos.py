"""Video metadata routes.

Exposes a metadata-only lookup used by the Home page's trim slider so its range
reflects the real video duration before a job runs. This does not download or
process anything.
"""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.services.video_metadata import (
    InvalidVideoUrl,
    MetadataUnavailable,
    fetch_metadata,
)

router = APIRouter(prefix="/videos", tags=["videos"])


class VideoMetadata(BaseModel):
    """Minimal video metadata for pre-fill of the trim slider."""

    title: str | None = None
    # Duration in seconds; None when the source does not report one.
    duration: float | None = None


@router.get("/metadata", response_model=VideoMetadata)
def get_video_metadata(url: str = Query(min_length=1)) -> VideoMetadata:
    """Return a video's title and duration without downloading it.

    Returns 400 for a malformed URL and 502 when the upstream extraction fails
    (network error, private/removed video, or the client being blocked).
    """
    try:
        info = fetch_metadata(url)
    except InvalidVideoUrl as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MetadataUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not fetch video metadata: {exc}",
        ) from exc
    return VideoMetadata(**info)
