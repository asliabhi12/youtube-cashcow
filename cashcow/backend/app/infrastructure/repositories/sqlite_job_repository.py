"""SQLite Job & Metadata Repository implementation."""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import uuid4

from app.core.config import AppConfig, get_app_config
from app.domain.repositories.job_repository import IJobRepository
from app.models.metadata import VideoMetadata
from app.models.destination import UploadSettings
from app.services.jobs import Job, job_store

logger = logging.getLogger(__name__)


def _now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteJobRepository(IJobRepository):
    """Concrete SQLite Job & Metadata Repository implementation."""

    def __init__(self, config: Optional[AppConfig] = None, connection: Optional[sqlite3.Connection] = None) -> None:
        self._config = config or get_app_config()
        self._connection = connection

    def _get_conn(self) -> tuple[sqlite3.Connection, bool]:
        if self._connection is not None:
            return self._connection, False
        db_path = self._config.db.sqlite_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn, True

    def create(self, url: str, profile_id: Optional[str] = None) -> Job:
        job = job_store.create(url, profile_id=profile_id or "custom")
        conn, should_close = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO jobs (id, created_at, updated_at) VALUES (?, ?, ?)",
                (job.id, _now_text(), _now_text()),
            )
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()
        return job

    def get_by_id(self, job_id: str) -> Optional[Job]:
        return job_store.get(job_id)

    def list_recent(self, limit: int = 50) -> Sequence[Job]:
        return job_store.list_recent(limit)

    def update_status(self, job_id: str, status: str, error: Optional[str] = None) -> Job:
        job_store.set_status(job_id, status, error)
        conn, should_close = self._get_conn()
        try:
            conn.execute(
                "UPDATE jobs SET updated_at = ? WHERE id = ?",
                (_now_text(), job_id),
            )
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()
        job = job_store.get(job_id)
        if job is None:
            raise ValueError(f"Job '{job_id}' not found")
        return job

    def save_metadata(self, job_id: str, metadata: VideoMetadata) -> VideoMetadata:
        from app.services.metadata import metadata_service
        metadata_service.set(job_id, metadata)

        conn, should_close = self._get_conn()
        try:
            tags_json = json.dumps(metadata.tags) if metadata.tags else "[]"
            conn.execute(
                """INSERT OR REPLACE INTO metadata (
                       id, job_id, title, description, tags, category, model, raw, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"meta_{job_id}",
                    job_id,
                    metadata.title,
                    metadata.description,
                    tags_json,
                    "",
                    metadata.model,
                    metadata.model_dump_json(),
                    _now_text(),
                ),
            )
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()
        return metadata

    def get_metadata(self, job_id: str) -> Optional[VideoMetadata]:
        from app.services.metadata import metadata_service
        return metadata_service.get(job_id)

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
        conn, should_close = self._get_conn()
        stamp = _now_text()
        try:
            conn.execute(
                """INSERT INTO upload_history (
                       job_id, destination_id, status, progress, video_id, video_url,
                       error, upload_settings, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    destination_id,
                    status,
                    progress,
                    video_id,
                    video_url,
                    error,
                    UploadSettings().model_dump_json(by_alias=True),
                    stamp,
                    stamp,
                ),
            )
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()
