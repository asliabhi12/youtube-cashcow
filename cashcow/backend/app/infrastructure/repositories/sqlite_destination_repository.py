"""SQLite Destination & OAuth Repository implementation."""

from datetime import datetime, timedelta, timezone
import logging
import re
import sqlite3
from typing import Optional, Sequence

from app.core.config import AppConfig, get_app_config
from app.domain.repositories.destination_repository import IDestinationRepository
from app.models.destination import (
    Destination,
    DestinationStatus,
    DestinationTokenRecord,
)

logger = logging.getLogger(__name__)
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
OAUTH_STATE_TTL = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_text() -> str:
    return _now().isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _slugify(value: str) -> str:
    slug = _SLUG_STRIP.sub("-", value.lower()).strip("-")
    return slug or "youtube-channel"


def _row_to_destination(row: sqlite3.Row) -> Destination:
    return Destination(
        id=row["id"],
        name=row["name"],
        channelTitle=row["channel_title"],
        channelId=row["channel_id"],
        thumbnail=row["thumbnail"] or "",
        description=row["description"] or "",
        platform="youtube",
        connectionStatus=row["connection_status"],
        tokenExpiresAt=_parse_dt(row["token_expires_at"]),
        lastSyncedAt=_parse_dt(row["last_synced_at"]),
        createdAt=_parse_dt(row["created_at"]) or _now(),
        updatedAt=_parse_dt(row["updated_at"]) or _now(),
    )


class SQLiteDestinationRepository(IDestinationRepository):
    """Concrete SQLite Destination Repository implementation."""

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

    def list_all(self) -> Sequence[Destination]:
        conn, should_close = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM destinations ORDER BY created_at ASC, channel_title ASC").fetchall()
        finally:
            if should_close:
                conn.close()
        return [_row_to_destination(row) for row in rows]

    def get_by_id(self, destination_id: str) -> Optional[Destination]:
        conn, should_close = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
        finally:
            if should_close:
                conn.close()
        return _row_to_destination(row) if row else None

    def get_token_record(self, destination_id: str) -> Optional[DestinationTokenRecord]:
        conn, should_close = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
        finally:
            if should_close:
                conn.close()
        if row is None:
            return None
        return DestinationTokenRecord(
            destination=_row_to_destination(row),
            access_token=row["access_token"],
            refresh_token=row["refresh_token"],
        )

    def upsert_connected_channel(
        self,
        *,
        channel_title: str,
        channel_id: str,
        thumbnail: str,
        description: str,
        access_token: str,
        refresh_token: str,
        token_expires_at: Optional[datetime],
    ) -> Destination:
        conn, should_close = self._get_conn()
        try:
            existing = conn.execute("SELECT * FROM destinations WHERE channel_id = ?", (channel_id,)).fetchone()
            stamp = _now_text()
            expires = token_expires_at.isoformat() if token_expires_at else None

            if existing is None:
                base_slug = _slugify(channel_title)
                candidate = base_slug
                suffix = 2
                while conn.execute("SELECT id FROM destinations WHERE id = ?", (candidate,)).fetchone() is not None:
                    candidate = f"{base_slug}-{suffix}"
                    suffix += 1
                destination_id = candidate

                conn.execute(
                    """INSERT INTO destinations (
                           id, name, channel_title, channel_id, thumbnail, description,
                           connection_status, access_token, refresh_token,
                           token_expires_at, last_synced_at, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        destination_id,
                        channel_title,
                        channel_title,
                        channel_id,
                        thumbnail,
                        description,
                        "connected",
                        access_token,
                        refresh_token,
                        expires,
                        stamp,
                        stamp,
                        stamp,
                    ),
                )
            else:
                destination_id = existing["id"]
                conn.execute(
                    """UPDATE destinations
                       SET name = ?, channel_title = ?, thumbnail = ?, description = ?,
                           connection_status = 'connected', access_token = ?,
                           refresh_token = ?, token_expires_at = ?,
                           last_synced_at = ?, updated_at = ?
                       WHERE id = ?""",
                    (
                        channel_title,
                        channel_title,
                        thumbnail,
                        description,
                        access_token,
                        refresh_token or existing["refresh_token"],
                        expires,
                        stamp,
                        stamp,
                        destination_id,
                    ),
                )

            if should_close:
                conn.commit()
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
        finally:
            if should_close:
                conn.close()
        return _row_to_destination(row)

    def update_tokens(
        self,
        destination_id: str,
        *,
        access_token: str,
        token_expires_at: Optional[datetime],
        refresh_token: Optional[str] = None,
    ) -> Destination:
        conn, should_close = self._get_conn()
        try:
            existing = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
            if existing is None:
                raise ValueError(f"Destination '{destination_id}' not found")

            stamp = _now_text()
            conn.execute(
                """UPDATE destinations
                   SET access_token = ?, refresh_token = ?, token_expires_at = ?,
                       connection_status = 'connected', updated_at = ?
                   WHERE id = ?""",
                (
                    access_token,
                    refresh_token or existing["refresh_token"],
                    token_expires_at.isoformat() if token_expires_at else None,
                    stamp,
                    destination_id,
                ),
            )
            if should_close:
                conn.commit()
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
        finally:
            if should_close:
                conn.close()
        return _row_to_destination(row)

    def mark_status(self, destination_id: str, status: DestinationStatus) -> None:
        conn, should_close = self._get_conn()
        try:
            conn.execute(
                "UPDATE destinations SET connection_status = ?, updated_at = ? WHERE id = ?",
                (status, _now_text(), destination_id),
            )
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

    def delete(self, destination_id: str) -> bool:
        conn, should_close = self._get_conn()
        try:
            cur = conn.execute("DELETE FROM destinations WHERE id = ?", (destination_id,))
            if should_close:
                conn.commit()
            count = cur.rowcount
        finally:
            if should_close:
                conn.close()
        return count > 0

    def store_oauth_state(self, state: str) -> None:
        self._cleanup_expired_oauth_states()
        conn, should_close = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO oauth_states (state, created_at) VALUES (?, ?)",
                (state, _now_text()),
            )
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

    def consume_oauth_state(self, state: str) -> bool:
        conn, should_close = self._get_conn()
        try:
            row = conn.execute("SELECT created_at FROM oauth_states WHERE state = ?", (state,)).fetchone()
            if row is None:
                return False

            created = _parse_dt(row["created_at"])
            conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

        if created is None or _now() - created > OAUTH_STATE_TTL:
            return False
        return True

    def _cleanup_expired_oauth_states(self) -> None:
        cutoff = (_now() - OAUTH_STATE_TTL).isoformat()
        conn, should_close = self._get_conn()
        try:
            conn.execute("DELETE FROM oauth_states WHERE created_at < ?", (cutoff,))
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()
