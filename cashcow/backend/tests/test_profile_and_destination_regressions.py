"""Regression tests for Profile legacy migration and YouTube OAuth Destination integration."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app.services import destinations as dest_service


def _get_dest_ids(data: dict) -> list[str]:
    """Helper to get allowed destination IDs from dict by alias or field name."""
    if "allowedDestinationIds" in data:
        return data["allowedDestinationIds"]
    return data.get("allowed_destination_ids", [])


def _ensure_oauth_destination() -> str:
    dest = dest_service.upsert_connected_channel(
        channel_title="Real OAuth Channel",
        channel_id="UC-real-oauth-123",
        thumbnail="",
        description="A real connected channel",
        access_token="valid-access-token",
        refresh_token="valid-refresh-token",
        token_expires_at=None,
    )
    return dest.id


def test_get_destinations_returns_list():
    client = TestClient(app)
    response = client.get("/destinations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_legacy_profile_migration_detects_and_strips_legacy_ids():
    """Verify legacy mock IDs (chotu-tv) are stripped and user warning is returned."""
    client = TestClient(app)

    payload = {
        "label": "Legacy Test Profile",
        "allowedDestinationIds": ["chotu-tv", "ramayani-rides"],
    }
    create_res = client.post("/profiles", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()

    assert _get_dest_ids(data) == []
    assert len(data.get("warnings", [])) > 0
    assert any("legacy destination" in w.lower() for w in data["warnings"])


def test_mixed_legacy_and_oauth_ids():
    """Verify mixed legacy + OAuth IDs keeps valid OAuth ID and strips legacy mock ID."""
    client = TestClient(app)
    oauth_id = _ensure_oauth_destination()

    payload = {
        "label": "Test Mixed Profile",
        "description": "Test profile with mixed destination IDs",
        "allowedDestinationIds": ["chotu-tv", oauth_id, "ramayani-rides"],
    }

    create_res = client.post("/profiles", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()

    dest_ids = _get_dest_ids(created)
    assert oauth_id in dest_ids
    assert "chotu-tv" not in dest_ids
    assert "ramayani-rides" not in dest_ids
    assert len(created.get("warnings", [])) > 0


def test_oauth_only_profile():
    """Verify profile with valid OAuth IDs has no migration warnings."""
    client = TestClient(app)
    oauth_id = _ensure_oauth_destination()

    payload = {
        "label": "OAuth Only Profile",
        "allowedDestinationIds": [oauth_id],
    }

    res = client.post("/profiles", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert _get_dest_ids(data) == [oauth_id]
    assert len(data.get("warnings", [])) == 0


def test_empty_destination_list():
    """Verify profile with empty destination list works without warnings."""
    client = TestClient(app)
    payload = {
        "label": "Empty Destinations Profile",
        "allowedDestinationIds": [],
    }

    res = client.post("/profiles", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert _get_dest_ids(data) == []
    assert len(data.get("warnings", [])) == 0


def test_profile_save_persistence_after_migration():
    """Verify custom profile save persists clean destination IDs on disk."""
    client = TestClient(app)
    oauth_id = _ensure_oauth_destination()

    # Create profile with legacy ID
    create_res = client.post(
        "/profiles",
        json={"label": "To Migrate Persistent", "allowedDestinationIds": ["chotu-tv", oauth_id]},
    )
    assert create_res.status_code == 201
    prof_id = create_res.json()["id"]

    # Re-fetch profile from disk
    get_res = client.get(f"/profiles/{prof_id}")
    assert get_res.status_code == 200
    fetched = get_res.json()

    # Verify on-disk loaded profile only has the valid OAuth ID
    assert _get_dest_ids(fetched) == [oauth_id]


def test_invalid_malformed_payload_rejection():
    """Verify malformed profile payloads are rejected with 422 (not silently swallowed)."""
    client = TestClient(app)
    malformed_payload = {
        "label": "Malformed",
        "unexpected_malformed_attribute": "invalid_value",
    }
    res = client.post("/profiles", json=malformed_payload)
    assert res.status_code == 422


def test_allowed_destinations_persistence_and_update():
    """Verify allowed destinations persist across save/reload, and editing updates correctly."""
    client = TestClient(app)
    channel_a = dest_service.upsert_connected_channel(
        channel_title="Channel A",
        channel_id="UC-chan-a-123",
        thumbnail="",
        description="Channel A",
        access_token="tok-a",
        refresh_token="ref-a",
        token_expires_at=None,
    )
    channel_b = dest_service.upsert_connected_channel(
        channel_title="Channel B",
        channel_id="UC-chan-b-456",
        thumbnail="",
        description="Channel B",
        access_token="tok-b",
        refresh_token="ref-b",
        token_expires_at=None,
    )

    # 1. Create profile with Channel A + Channel B
    create_payload = {
        "label": "Multi-Channel Profile",
        "allowedDestinationIds": [channel_a.id, channel_b.id],
    }
    create_res = client.post("/profiles", json=create_payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    prof_id = created_data["id"]

    # Verify reload returns both Channel A & Channel B
    reload_res1 = client.get(f"/profiles/{prof_id}")
    assert reload_res1.status_code == 200
    reloaded_data1 = reload_res1.json()

    assert _get_dest_ids(reloaded_data1) == [channel_a.id, channel_b.id]
    assert reloaded_data1.get("allowedDestinationIds") == [channel_a.id, channel_b.id]

    # 2. Edit profile: remove Channel B (keep only Channel A)
    update_payload = {
        "label": "Multi-Channel Profile",
        "allowedDestinationIds": [channel_a.id],
    }
    update_res = client.put(f"/profiles/{prof_id}", json=update_payload)
    assert update_res.status_code == 200

    # Verify reload returns ONLY Channel A
    reload_res2 = client.get(f"/profiles/{prof_id}")
    assert reload_res2.status_code == 200
    reloaded_data2 = reload_res2.json()

    assert _get_dest_ids(reloaded_data2) == [channel_a.id]
    assert reloaded_data2.get("allowedDestinationIds") == [channel_a.id]

