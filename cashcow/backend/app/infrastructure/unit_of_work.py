"""Concrete SQLite Unit of Work context manager implementation."""

import logging
import sqlite3
from typing import Any, Callable, List, Optional

from app.core.config import AppConfig, get_app_config
from app.domain.unit_of_work import IUnitOfWork
from app.infrastructure.repositories.sqlite_destination_repository import SQLiteDestinationRepository
from app.infrastructure.repositories.sqlite_job_repository import SQLiteJobRepository
from app.infrastructure.repositories.sqlite_memory_repository import SQLiteMemoryRepository
from app.infrastructure.repositories.yaml_profile_repository import YAMLProfileRepository

logger = logging.getLogger(__name__)


class SQLiteUnitOfWork(IUnitOfWork):
    """Coordinates SQLite and File operations with single transactional connection & compensation handlers."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config or get_app_config()
        self._conn: Optional[sqlite3.Connection] = None
        self._compensations: List[Callable[[], None]] = []
        self._committed = False

        # Initial default instances (non-transactional)
        self.profiles = YAMLProfileRepository(self._config)
        self.destinations = SQLiteDestinationRepository(self._config)
        self.jobs = SQLiteJobRepository(self._config)
        self.memory = SQLiteMemoryRepository(self._config)

    def __enter__(self) -> "SQLiteUnitOfWork":
        db_path = self._config.db.sqlite_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("BEGIN TRANSACTION")

        self.profiles = YAMLProfileRepository(self._config)
        self.destinations = SQLiteDestinationRepository(self._config, connection=self._conn)
        self.jobs = SQLiteJobRepository(self._config, connection=self._conn)
        self.memory = SQLiteMemoryRepository(self._config, connection=self._conn)

        self._compensations.clear()
        self._committed = False
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if exc_type is not None and not self._committed:
                self.rollback()
            elif not self._committed:
                self.commit()
        finally:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def commit(self) -> None:
        if self._conn is not None and not self._committed:
            self._conn.commit()
            self._committed = True
            logger.info("[SQLiteUnitOfWork] Transaction committed atomically")

    def rollback(self) -> None:
        if self._conn is not None:
            try:
                self._conn.rollback()
            except Exception as exc:
                logger.error("[SQLiteUnitOfWork] Exception rolling back SQLite transaction: %s", exc)

        logger.warning("[SQLiteUnitOfWork] Executing %d compensation actions", len(self._compensations))
        for comp in reversed(self._compensations):
            try:
                comp()
            except Exception as exc:
                logger.error("[SQLiteUnitOfWork] Error running compensation action %s: %s", comp, exc)
        self._compensations.clear()

    def add_compensation_action(self, action: Callable[[], None]) -> None:
        self._compensations.append(action)
