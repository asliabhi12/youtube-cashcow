"""SQLite Agent Memory & Workflow Event Repository implementation."""

from datetime import datetime, timezone
import logging
import sqlite3
from typing import Optional, Sequence

from app.core.config import AppConfig, get_app_config
from app.domain.repositories.memory_repository import IMemoryRepository
from app.models.agent_memory import AgentMemoryRecord, WorkflowEvent
from app.infrastructure.repositories.legacy import MemoryRepository, WorkflowEventRepository

logger = logging.getLogger(__name__)

_memory_repo = MemoryRepository()
_workflow_event_repo = WorkflowEventRepository()


def _now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteMemoryRepository(IMemoryRepository):
    """Concrete SQLite Agent Memory & Workflow Event Repository implementation."""

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

    def record_event(
        self,
        job_id: str,
        stage: str,
        status: str,
        finished_at: Optional[datetime] = None,
    ) -> WorkflowEvent:
        fin_str = finished_at.isoformat() if finished_at else None
        _workflow_event_repo.append(job_id, stage, status, finished_at=fin_str)
        conn, should_close = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO workflow_events (job_id, stage, status, finished_at, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (job_id, stage, status, fin_str, _now_text()),
            )
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()
        return WorkflowEvent(id=None, job_id=job_id, stage=stage, status=status, finished_at=finished_at)

    def get_events(self, job_id: str) -> Sequence[WorkflowEvent]:
        conn, should_close = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM workflow_events WHERE job_id = ? ORDER BY id ASC",
                (job_id,),
            ).fetchall()
        finally:
            if should_close:
                conn.close()
        return [
            WorkflowEvent(
                id=r["id"],
                job_id=r["job_id"],
                stage=r["stage"],
                status=r["status"],
            )
            for r in rows
        ]

    def store_agent_memory(
        self,
        job_id: str,
        task: str,
        status: str,
        output_summary: Optional[str] = None,
        model: Optional[str] = None,
        artifact_path: Optional[str] = None,
    ) -> AgentMemoryRecord:
        _memory_repo.save(
            job_id, task, status, output_summary=output_summary, model=model, artifact_path=artifact_path
        )
        conn, should_close = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO agent_memory (job_id, task, status, output_summary, model, artifact_path, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (job_id, task, status, output_summary, model, artifact_path, _now_text()),
            )
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()
        return AgentMemoryRecord(
            id=None,
            job_id=job_id,
            task=task,
            status=status,
            output_summary=output_summary,
            model=model,
            artifact_path=artifact_path,
        )

    def get_agent_memory(self, job_id: str, task: Optional[str] = None) -> Sequence[AgentMemoryRecord]:
        conn, should_close = self._get_conn()
        try:
            if task:
                rows = conn.execute(
                    "SELECT * FROM agent_memory WHERE job_id = ? AND task = ? ORDER BY id ASC",
                    (job_id, task),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agent_memory WHERE job_id = ? ORDER BY id ASC",
                    (job_id,),
                ).fetchall()
        finally:
            if should_close:
                conn.close()
        return [
            AgentMemoryRecord(
                id=r["id"],
                job_id=r["job_id"],
                task=r["task"],
                status=r["status"],
                output_summary=r["output_summary"],
                model=r["model"],
                artifact_path=r["artifact_path"],
            )
            for r in rows
        ]
