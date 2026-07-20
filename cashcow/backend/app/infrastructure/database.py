import logging
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[4] / "cashcow.db"



logger = logging.getLogger(__name__)


_init_lock = threading.Lock()
_init_done = False


def _get_connection() -> sqlite3.Connection:
    resolved = str(DB_PATH.resolve())
    logger.info(
        "[_get_connection] connecting to %s (file_exists=%s, init_done=%s)",
        resolved,
        DB_PATH.exists(),
        _init_done,
    )
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    
    # Log every discovered table
    try:
        tables = [row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        logger.info("[_get_connection] resolved database path: %s", resolved)
        logger.info("[_get_connection] discovered tables: %s", tables)
    except Exception as exc:
        logger.error("[_get_connection] failed to list tables: %s", exc)
        
    return conn


def init_database() -> None:
    global _init_done
    resolved = str(DB_PATH.resolve())
    
    # Verify if database exists and contains the expected tables
    db_ok = False
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            conn.close()
            required = {"jobs", "metadata", "workflow_events", "agent_memory"}
            if required.issubset(tables):
                db_ok = True
        except Exception:
            db_ok = False

    if _init_done and db_ok:
        logger.info("[init_database] skipped (already initialised and verified, db=%s)", resolved)
        return
        
    with _init_lock:
        # Re-check db_ok inside lock
        db_ok = False
        if DB_PATH.exists():
            try:
                conn = sqlite3.connect(str(DB_PATH))
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                conn.close()
                required = {"jobs", "metadata", "workflow_events", "agent_memory"}
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
            DB_PATH.exists(),
        )
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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
        """)
        conn.commit()
        conn.close()
        _init_done = True
        logger.info("[init_database] schema created at %s", resolved)


def reset_database_for_testing() -> None:
    global _init_done
    resolved = str(DB_PATH.resolve())
    logger.info("[reset_database_for_testing] resetting db at %s", resolved)
    conn = _get_connection()
    conn.executescript("""
        DROP TABLE IF EXISTS agent_memory;
        DROP TABLE IF EXISTS workflow_events;
        DROP TABLE IF EXISTS metadata;
        DROP TABLE IF EXISTS jobs;
    """)
    conn.commit()
    conn.close()
    _init_done = False
    if DB_PATH.exists():
        DB_PATH.unlink()
        logger.info("[reset_database_for_testing] deleted %s", resolved)
