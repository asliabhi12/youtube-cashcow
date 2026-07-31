"""Persistent YouTube destination storage."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.infrastructure.database import _get_connection, init_database
from app.models.destination import (
    Destination,
    DestinationStatus,
    DestinationTokenRecord,
    JobDestinationStatus,
    UploadSettings,
)

logger = logging.getLogger(__name__)
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


class DestinationNotFoundError(Exception):
    """Raised when a destination id does not exist."""


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


def _row_to_destination(row) -> Destination:
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


def _unique_id(conn, base: str, existing_id: str | None = None) -> str:
    candidate = base
    suffix = 2
    while True:
        row = conn.execute("SELECT id FROM destinations WHERE id = ?", (candidate,)).fetchone()
        if row is None or row["id"] == existing_id:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def list_destinations() -> list[Destination]:
    init_database()
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM destinations ORDER BY created_at ASC, channel_title ASC"
    ).fetchall()
    logger.info("[list_destinations] found %d row(s)", len(rows))
    for r in rows:
        logger.info("[list_destinations] row id=%s title=%s channel_id=%s", r["id"], r["channel_title"], r["channel_id"])
    conn.close()
    result = [_row_to_destination(row) for row in rows]
    logger.info("[list_destinations] returning %d Destination(s)", len(result))
    return result


def get_destination(destination_id: str) -> Destination | None:
    init_database()
    conn = _get_connection()
    row = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
    conn.close()
    return _row_to_destination(row) if row else None


def get_destination_record(destination_id: str) -> DestinationTokenRecord | None:
    init_database()
    conn = _get_connection()
    row = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return DestinationTokenRecord(
        destination=_row_to_destination(row),
        access_token=row["access_token"],
        refresh_token=row["refresh_token"],
    )


def destination_exists(destination_id: str) -> bool:
    return get_destination(destination_id) is not None


def default_destination_ids() -> list[str]:
    init_database()
    conn = _get_connection()
    rows = conn.execute(
        """SELECT id FROM destinations
           WHERE connection_status = 'connected'
           ORDER BY created_at ASC"""
    ).fetchall()
    conn.close()
    return [row["id"] for row in rows[:1]]


def upsert_connected_channel(
    *,
    channel_title: str,
    channel_id: str,
    thumbnail: str,
    description: str,
    access_token: str,
    refresh_token: str,
    token_expires_at: datetime | None,
) -> Destination:
    """Create or update a connected YouTube channel and its credentials."""
    init_database()
    conn = _get_connection()
    existing = conn.execute(
        "SELECT * FROM destinations WHERE channel_id = ?", (channel_id,)
    ).fetchone()
    stamp = _now_text()
    expires = token_expires_at.isoformat() if token_expires_at else None
    if existing is None:
        destination_id = _unique_id(conn, _slugify(channel_title))
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
    conn.commit()
    logger.info("[upsert_connected_channel] committed id=%s title=%s channel_id=%s", destination_id, channel_title, channel_id)
    row = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
    conn.close()
    if row is None:
        logger.error("[upsert_connected_channel] row vanished id=%s", destination_id)
        raise DestinationNotFoundError(destination_id)
    logger.info("[upsert_connected_channel] re-read ok keys=%s", list(row.keys()))
    return _row_to_destination(row)


def update_tokens(
    destination_id: str,
    *,
    access_token: str,
    token_expires_at: datetime | None,
    refresh_token: str | None = None,
) -> Destination:
    init_database()
    conn = _get_connection()
    existing = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
    if existing is None:
        conn.close()
        raise DestinationNotFoundError(destination_id)
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
    conn.commit()
    row = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
    conn.close()
    if row is None:
        raise DestinationNotFoundError(destination_id)
    return _row_to_destination(row)


def mark_status(destination_id: str, status: DestinationStatus) -> None:
    init_database()
    conn = _get_connection()
    conn.execute(
        "UPDATE destinations SET connection_status = ?, updated_at = ? WHERE id = ?",
        (status, _now_text(), destination_id),
    )
    conn.commit()
    conn.close()


OAUTH_STATE_TTL = timedelta(minutes=15)


def store_oauth_state(state: str) -> None:
    init_database()
    _cleanup_expired_oauth_states()
    conn = _get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO oauth_states (state, created_at) VALUES (?, ?)",
        (state, _now_text()),
    )
    conn.commit()
    conn.close()


def consume_oauth_state(state: str) -> bool:
    init_database()
    conn = _get_connection()
    row = conn.execute(
        "SELECT created_at FROM oauth_states WHERE state = ?", (state,)
    ).fetchone()
    if row is None:
        conn.close()
        return False
    created = _parse_dt(row["created_at"])
    conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    conn.commit()
    conn.close()
    if created is None or _now() - created > OAUTH_STATE_TTL:
        return False
    return True


def _cleanup_expired_oauth_states() -> None:
    cutoff = (_now() - OAUTH_STATE_TTL).isoformat()
    conn = _get_connection()
    deleted = conn.execute(
        "DELETE FROM oauth_states WHERE created_at < ?", (cutoff,)
    ).rowcount
    conn.commit()
    conn.close()
    if deleted:
        logger.info("[oauth] cleaned %d expired state(s)", deleted)


def delete_destination(destination_id: str) -> None:
    init_database()
    conn = _get_connection()
    cur = conn.execute("DELETE FROM destinations WHERE id = ?", (destination_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise DestinationNotFoundError(destination_id)


def record_upload(
    *,
    job_id: str,
    destination_id: str,
    status: JobDestinationStatus,
    progress: int,
    upload_settings: UploadSettings,
    video_id: str | None = None,
    video_url: str | None = None,
    error: str | None = None,
) -> None:
    init_database()
    stamp = _now_text()
    conn = _get_connection()
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
            upload_settings.model_dump_json(by_alias=True),
            stamp,
            stamp,
        ),
    )
    conn.commit()
    conn.close()

