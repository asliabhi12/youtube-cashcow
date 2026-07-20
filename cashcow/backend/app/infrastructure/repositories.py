import logging
from datetime import datetime, timezone

from app.infrastructure.database import DB_PATH, _get_connection

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobRepository:

    def upsert(self, job_id: str) -> None:
        logger.info("[JobRepository.upsert] db=%s job=%s", DB_PATH.resolve(), job_id)
        conn = _get_connection()
        conn.execute(
            """INSERT INTO jobs (id, created_at, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at""",
            (job_id, _now(), _now()),
        )
        conn.commit()
        conn.close()

    def get(self, job_id: str) -> dict | None:
        logger.info("[JobRepository.get] db=%s job=%s", DB_PATH.resolve(), job_id)
        conn = _get_connection()
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
        return dict(row) if row else None


class MetadataRepository:

    def save(self, job_id: str, **fields: str | None) -> None:
        logger.info("[MetadataRepository.save] db=%s job=%s fields=%s", DB_PATH.resolve(), job_id, list(fields))
        conn = _get_connection()
        conn.execute(
            """INSERT INTO metadata (id, job_id, title, description, tags, category, model, raw)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   title=excluded.title, description=excluded.description,
                   tags=excluded.tags, category=excluded.category,
                   model=excluded.model, raw=excluded.raw""",
            (
                job_id,
                job_id,
                fields.get("title"),
                fields.get("description"),
                fields.get("tags"),
                fields.get("category"),
                fields.get("model"),
                fields.get("raw"),
            ),
        )
        conn.commit()
        conn.close()

    def get(self, job_id: str) -> dict | None:
        logger.info("[MetadataRepository.get] db=%s job=%s", DB_PATH.resolve(), job_id)
        conn = _get_connection()
        row = conn.execute(
            "SELECT * FROM metadata WHERE job_id = ? ORDER BY created_at DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None


class WorkflowEventRepository:

    def append(
        self,
        job_id: str,
        stage: str,
        status: str,
        *,
        finished_at: str | None = None,
    ) -> None:
        logger.info("[WorkflowEventRepository.append] db=%s job=%s stage=%s status=%s", DB_PATH.resolve(), job_id, stage, status)
        conn = _get_connection()
        conn.execute(
            "INSERT INTO workflow_events (job_id, stage, status, finished_at) VALUES (?, ?, ?, ?)",
            (job_id, stage, status, finished_at),
        )
        conn.commit()
        conn.close()

    def latest_event(self, job_id: str) -> dict | None:
        logger.info("[WorkflowEventRepository.latest_event] db=%s job=%s", DB_PATH.resolve(), job_id)
        conn = _get_connection()
        row = conn.execute(
            """SELECT * FROM workflow_events
               WHERE job_id = ?
               ORDER BY id DESC LIMIT 1""",
            (job_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None


class MemoryRepository:

    def save(
        self,
        job_id: str,
        task: str,
        status: str,
        *,
        output_summary: str | None = None,
        model: str | None = None,
        artifact_path: str | None = None,
    ) -> None:
        logger.info("[MemoryRepository.save] db=%s job=%s task=%s status=%s", DB_PATH.resolve(), job_id, task, status)
        conn = _get_connection()
        conn.execute(
            """INSERT INTO agent_memory (job_id, task, status, output_summary, model, artifact_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (job_id, task, status, output_summary, model, artifact_path),
        )
        conn.commit()
        conn.close()

    def is_completed(self, job_id: str, task: str) -> bool:
        logger.info("[MemoryRepository.is_completed] db=%s job=%s task=%s", DB_PATH.resolve(), job_id, task)
        conn = _get_connection()
        row = conn.execute(
            """SELECT status FROM agent_memory
               WHERE job_id = ? AND task = ?
               ORDER BY id DESC LIMIT 1""",
            (job_id, task),
        ).fetchone()
        conn.close()
        return row is not None and row["status"] == "completed"

    def get_unfinished_jobs(self) -> list[str]:
        logger.info("[MemoryRepository.get_unfinished_jobs] db=%s", DB_PATH.resolve())
        conn = _get_connection()
        rows = conn.execute(
            """SELECT DISTINCT m.job_id
               FROM agent_memory m
               WHERE NOT EXISTS (
                   SELECT 1 FROM workflow_events w
                   WHERE w.job_id = m.job_id
                     AND w.stage = 'pipeline'
                     AND w.status = 'completed'
               )
               ORDER BY m.job_id""",
        ).fetchall()
        conn.close()
        return [r["job_id"] for r in rows]

    def get_task(self, job_id: str, task: str) -> dict | None:
        logger.info("[MemoryRepository.get_task] db=%s job=%s task=%s", DB_PATH.resolve(), job_id, task)
        conn = _get_connection()
        row = conn.execute(
            """SELECT * FROM agent_memory
               WHERE job_id = ? AND task = ?
               ORDER BY id DESC LIMIT 1""",
            (job_id, task),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def clear_job(self, job_id: str) -> None:
        logger.info("[MemoryRepository.clear_job] db=%s job=%s", DB_PATH.resolve(), job_id)
        conn = _get_connection()
        conn.execute("DELETE FROM agent_memory WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM workflow_events WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM metadata WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
