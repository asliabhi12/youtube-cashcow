import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_app_config

logger = logging.getLogger(__name__)


class _DBPathProxy:
    @property
    def _target(self) -> Path:
        return get_db_path()

    def resolve(self):
        return self._target.resolve()

    def exists(self):
        return self._target.exists()

    def unlink(self, missing_ok=False):
        return self._target.unlink(missing_ok=missing_ok)

    @property
    def parent(self):
        return self._target.parent

    def __str__(self):
        return str(self._target)

    def __fspath__(self):
        return str(self._target)


DB_PATH = _DBPathProxy()

_init_lock = threading.Lock()
_init_done = False


def get_db_path() -> Path:
    return get_app_config().db.sqlite_path


def _get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    resolved = str(db_path.resolve())
    logger.info(
        "[_get_connection] connecting to %s (file_exists=%s, init_done=%s)",
        resolved,
        db_path.exists(),
        _init_done,
    )
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    try:
        tables = [row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        logger.info("[_get_connection] resolved database path: %s", resolved)
        logger.info("[_get_connection] discovered tables: %s", tables)
    except Exception as exc:
        logger.error("[_get_connection] failed to list tables: %s", exc)

    return conn


def init_database() -> None:
    global _init_done
    db_path = get_db_path()
    resolved = str(db_path.resolve())

    db_ok = False
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            conn.close()
            required = {
                "jobs",
                "metadata",
                "workflow_events",
                "agent_memory",
                "destinations",
                "upload_history",
                "oauth_states",
            }
            if required.issubset(tables):
                db_ok = True
        except Exception:
            db_ok = False

    if _init_done and db_ok:
        logger.info("[init_database] skipped (already initialised and verified, db=%s)", resolved)
        return

    with _init_lock:
        db_ok = False
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                conn.close()
                required = {
                    "jobs",
                    "metadata",
                    "workflow_events",
                    "agent_memory",
                    "destinations",
                    "upload_history",
                    "oauth_states",
                }
                if required.issubset(tables):
                    db_ok = True
            except Exception:
                db_ok = False

        if _init_done and db_ok:
            logger.info("[init_database] skipped (already initialised and verified, db=%s)", resolved)
            return

        logger.info(
            "[init_database] creating schema at %s (file_exists=%s)",
            resolved,
            db_path.exists(),
        )
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _get_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS metadata (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                title TEXT,
                description TEXT,
                tags TEXT,
                category TEXT,
                model TEXT,
                raw TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS workflow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                finished_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS agent_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL,
                output_summary TEXT,
                model TEXT,
                artifact_path TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );

            CREATE INDEX IF NOT EXISTS idx_agent_memory_job_task ON agent_memory(job_id, task);
            CREATE INDEX IF NOT EXISTS idx_workflow_events_job ON workflow_events(job_id);

            CREATE TABLE IF NOT EXISTS destinations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                channel_title TEXT NOT NULL,
                channel_id TEXT NOT NULL UNIQUE,
                thumbnail TEXT,
                description TEXT,
                connection_status TEXT NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                token_expires_at TEXT,
                last_synced_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS upload_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                destination_id TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                video_id TEXT,
                video_url TEXT,
                error TEXT,
                upload_settings TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id),
                FOREIGN KEY (destination_id) REFERENCES destinations(id)
            );

            CREATE INDEX IF NOT EXISTS idx_upload_history_job ON upload_history(job_id);
            CREATE INDEX IF NOT EXISTS idx_upload_history_destination ON upload_history(destination_id);

            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_oauth_states_created ON oauth_states(created_at);
        """)
        conn.commit()

        cur = conn.execute("SELECT COUNT(*) FROM destinations")
        count = cur.fetchone()[0]
        rows = [dict(r) for r in conn.execute("SELECT * FROM destinations").fetchall()]
        logger.info("[init_database] Absolute SQLite database path: %s", resolved)
        logger.info("[init_database] Current destinations count: %d", count)

        conn.close()
        _init_done = True
        logger.info("[init_database] schema created at %s", resolved)


def reset_database_for_testing() -> None:
    global _init_done
    db_path = get_db_path()
    resolved = str(db_path.resolve())
    logger.info("[reset_database_for_testing] resetting db at %s", resolved)
    conn = _get_connection()
    conn.executescript("""
        DROP TABLE IF EXISTS agent_memory;
        DROP TABLE IF EXISTS workflow_events;
        DROP TABLE IF EXISTS metadata;
        DROP TABLE IF EXISTS upload_history;
        DROP TABLE IF EXISTS destinations;
        DROP TABLE IF EXISTS jobs;
        DROP TABLE IF EXISTS oauth_states;
    """)
    conn.commit()
    conn.close()
    _init_done = False
    if db_path.exists():
        try:
            db_path.unlink()
            logger.info("[reset_database_for_testing] deleted %s", resolved)
        except OSError:
            pass
