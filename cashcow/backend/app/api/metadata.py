"""Per-job AI metadata routes."""

from fastapi import APIRouter, HTTPException, status

from app.models.metadata import MetadataCreate, MetadataUpdate, VideoMetadata
from app.services.metadata import MetadataNotFoundError, metadata_service
from app.services.jobs import job_store

router = APIRouter(prefix="/jobs/{job_id}/metadata", tags=["metadata"])


def _require_job(job_id: str) -> None:
    if job_store.get(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


@router.post("", response_model=VideoMetadata, status_code=status.HTTP_201_CREATED)
def create_metadata(job_id: str, payload: MetadataCreate | None = None) -> VideoMetadata:
    _require_job(job_id)
    metadata = metadata_service.generate(job_id, payload)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Metadata generation unavailable",
        )
    return metadata


@router.get("", response_model=VideoMetadata)
def get_metadata(job_id: str) -> VideoMetadata:
    _require_job(job_id)
    metadata = metadata_service.get(job_id)
    if metadata is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metadata not found")
    return metadata


@router.put("", response_model=VideoMetadata)
def update_metadata(job_id: str, payload: MetadataUpdate) -> VideoMetadata:
    _require_job(job_id)
    try:
        return metadata_service.update(job_id, payload)
    except MetadataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/regenerate", response_model=VideoMetadata)
def regenerate_metadata(job_id: str) -> VideoMetadata:
    _require_job(job_id)
    metadata = metadata_service.regenerate(job_id)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Metadata generation unavailable",
        )
    return metadata
