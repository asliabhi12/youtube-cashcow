"""Tests for CashCow public demo mode and authentication authorization."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth.config import get_admin_username, get_admin_password

client = TestClient(app)


def test_public_demo_mode_readonly_endpoints():
    """Verify that unauthenticated users can browse read-only endpoints in Demo Mode."""
    # Health check
    assert client.get("/health").status_code == 200

    # Profiles list
    profiles_resp = client.get("/profiles")
    assert profiles_resp.status_code == 200

    # Destinations list
    dest_resp = client.get("/destinations")
    assert dest_resp.status_code == 200

    # Settings
    settings_resp = client.get("/settings")
    assert settings_resp.status_code == 200

    # Jobs list
    jobs_resp = client.get("/jobs")
    assert jobs_resp.status_code == 200


def test_protected_action_endpoints_require_login():
    """Verify that write operations and protected actions return 401 when unauthenticated."""
    invalid_headers = {"Authorization": "Bearer invalid_token_str"}

    # Creating job / starting workflow
    create_job_resp = client.post(
        "/jobs",
        json={"url": "https://example.com/video", "profile_id": "youtube_shorts_standard", "export_quality": "1080p"},
        headers=invalid_headers,
    )
    assert create_job_resp.status_code == 401
    assert create_job_resp.json()["detail"] == "Please sign in to continue."

    # Creating profile
    create_profile_resp = client.post(
        "/profiles",
        json={"label": "New Profile"},
        headers=invalid_headers,
    )
    assert create_profile_resp.status_code == 401
    assert create_profile_resp.json()["detail"] == "Please sign in to continue."

    # Connecting destination
    connect_resp = client.post("/destinations/connect", headers=invalid_headers)
    assert connect_resp.status_code == 401
    assert connect_resp.json()["detail"] == "Please sign in to continue."

    # Updating settings
    settings_resp = client.put(
        "/settings",
        json={"last_profile": "youtube_shorts_standard"},
        headers=invalid_headers,
    )
    assert settings_resp.status_code == 401
    assert settings_resp.json()["detail"] == "Please sign in to continue."


def test_authenticated_protected_actions():
    """Verify that authenticated requests succeed on protected endpoints."""
    username = get_admin_username()
    password = get_admin_password()

    # Login
    login_resp = client.post("/auth/login", json={"username": username, "password": password, "remember_me": False})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]

    # Authenticated settings update
    settings_resp = client.put("/settings", json={"last_profile": None}, cookies={"cashcow_session": token})
    assert settings_resp.status_code == 200
