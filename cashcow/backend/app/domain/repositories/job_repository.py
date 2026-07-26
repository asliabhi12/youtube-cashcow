"""Job & Metadata Repository interface contract."""

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from app.models.metadata import VideoMetadata
from app.services.jobs import Job


class IJobRepository(ABC):
    """Encapsulates job pipeline state, execution status, and generated metadata."""

    @abstractmethod
    def create(self, url: str, profile_id: Optional[str] = None) -> Job:
        """Create and initialize a new pipeline job entity."""
        pass

    @abstractmethod
    def get_by_id(self, job_id: str) -> Optional[Job]:
        """Fetch job entity by ID."""
        pass

    @abstractmethod
    def list_recent(self, limit: int = 50) -> Sequence[Job]:
        """List recent job entities."""
        pass

    @abstractmethod
    def update_status(self, job_id: str, status: str, error: Optional[str] = None) -> Job:
        """Update job status and optional error details."""
        pass

    @abstractmethod
    def save_metadata(self, job_id: str, metadata: VideoMetadata) -> VideoMetadata:
        """Persist AI-generated video metadata for a job."""
        pass

    @abstractmethod
    def get_metadata(self, job_id: str) -> Optional[VideoMetadata]:
        """Fetch video metadata for a job."""
        pass

    @abstractmethod
    def record_upload_history(
        self,
        *,
        job_id: str,
        destination_id: str,
        status: str,
        progress: int,
        video_id: Optional[str] = None,
        video_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record an upload attempt for a job destination."""
        pass
