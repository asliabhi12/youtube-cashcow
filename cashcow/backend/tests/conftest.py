"""Test configuration: seeds a default test destination for every test session."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database import init_database
from app.services import destinations as dest_service


def _seed_test_destination() -> None:
    """Ensure at least one connected YouTube channel exists in SQLite.

    Many tests rely on ``default_destination_ids()`` returning a non-empty
    list so that jobs created without explicit destination_ids still go
    through the upload code path.
    """
    init_database()
    existing = dest_service.list_destinations()
    if any(d.name == "Test Channel" for d in existing):
        return
    dest_service.upsert_connected_channel(
        channel_title="Test Channel",
        channel_id="UC-test-channel-default",
        thumbnail="",
        description="Default test destination",
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        token_expires_at=None,
    )


_seed_test_destination()
