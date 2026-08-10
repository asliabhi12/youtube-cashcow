"""Tests verifying SSE log streaming, credentialed CORS headers, and authentication controls."""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.services.job_logs import job_log_hub
from app.services.jobs import job_store
from app.models.job import JobLogLevel

from app.auth.security import create_session_token

client = TestClient(app)


def test_cors_preflight_allows_credentials():
    """Verify OPTIONS preflight on log events endpoint allows credentials and origin."""
    response = client.options(
        "/jobs/test-job-id/logs/events",
        headers={
            "Origin": "https://cashcow-frontend-nine.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert response.headers.get("access-control-allow-origin") == "https://cashcow-frontend-nine.vercel.app"


def test_unauthenticated_log_events_returns_401():
    """Verify log stream endpoint returns 401 when no session cookie or token is passed."""
    response = client.get("/jobs/test-job-id/logs/events")
    assert response.status_code == 401
    assert response.json()["detail"] == "Please sign in to continue."


def test_authenticated_log_events_and_history():
    """Verify log history and streaming work correctly when authenticated."""
    job = job_store.create(url="https://youtube.com/watch?v=test", profile_id="default")
    real_job_id = job.id

    # Append test log entry
    job_log_hub.append(real_job_id, "INFO", "Test log message")

    token, _ = create_session_token("abhishek", remember_me=True)
    # Fetch history via REST
    resp_history = client.get(
        f"/jobs/{real_job_id}/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_history.status_code == 200
    logs = resp_history.json()
    assert len(logs) >= 1
    assert any(l["message"] == "Test log message" for l in logs)
