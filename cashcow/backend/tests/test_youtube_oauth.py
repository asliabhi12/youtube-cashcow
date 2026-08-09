"""Tests for the MVP YouTube OAuth connection flow."""

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import youtube_upload_config
from app.main import app
from app.services import youtube_oauth


class StubResponse:
    def __init__(self, payload, headers=None):
        self._payload = payload
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_youtube_auth_start_redirects_to_google_with_upload_scope(monkeypatch):
    monkeypatch.setattr(youtube_oauth, "get_config_value", lambda name: "client-id")

    response = TestClient(app).get("/youtube/auth/start", follow_redirects=False)

    assert response.status_code == 307
    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    scope = query["scope"][0]
    assert youtube_oauth.YOUTUBE_UPLOAD_SCOPE in scope
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["response_type"] == ["code"]
    assert "state" in query


def test_google_oauth_callback_creates_destination_and_redirects(monkeypatch):
    from app.services import destinations as dest_service

    stored = {}
    captured = {}
    state = "known-state-google"
    dest_service.store_oauth_state(state)
    monkeypatch.setattr(youtube_oauth, "get_config_value", lambda name: f"{name}-value")
    monkeypatch.setattr(youtube_oauth, "set_local_config_value", lambda key, value: stored.update({key: value}))

    token_response_calls = 0

    def fake_urlopen(request, timeout):
        nonlocal token_response_calls
        if request.data:
            captured["body"] = request.data.decode("utf-8")
        captured["headers"] = dict(request.headers)
        assert timeout == youtube_oauth.REQUEST_TIMEOUT_SECONDS
        token_response_calls += 1
        if token_response_calls == 1:
            return StubResponse(
                {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "scope": youtube_oauth.YOUTUBE_UPLOAD_SCOPE,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                }
            )
        return StubResponse(
            {
                "items": [
                    {
                        "id": "UC-test-channel-oauth",
                        "snippet": {
                            "title": "OAuth Test Channel",
                            "description": "A test channel via OAuth",
                            "thumbnails": {"default": {"url": "https://example.com/thumb.jpg"}},
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr(youtube_oauth, "urlopen", fake_urlopen)

    response = TestClient(app).get(f"/oauth/google/callback?code=abc&state={state}", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == youtube_upload_config.FRONTEND_DESTINATIONS_URL
    assert stored.get("YOUTUBE_REFRESH_TOKEN") == "refresh-token"

    dests = dest_service.list_destinations()
    assert any(d.channel_id == "UC-test-channel-oauth" for d in dests)


def test_youtube_auth_callback_exchanges_code_and_stores_config(monkeypatch):
    from app.services import destinations as dest_service

    stored = {}
    captured = {}
    state = "known-state-legacy"
    dest_service.store_oauth_state(state)
    monkeypatch.setattr(youtube_oauth, "get_config_value", lambda name: f"{name}-value")
    monkeypatch.setattr(youtube_oauth, "set_local_config_value", lambda key, value: stored.update({key: value}))

    token_response_calls = 0

    def fake_urlopen(request, timeout):
        nonlocal token_response_calls
        if request.data:
            captured["body"] = request.data.decode("utf-8")
        captured["headers"] = dict(request.headers)
        assert timeout == youtube_oauth.REQUEST_TIMEOUT_SECONDS
        token_response_calls += 1
        if token_response_calls == 1:
            return StubResponse(
                {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "scope": youtube_oauth.YOUTUBE_UPLOAD_SCOPE,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                }
            )
        return StubResponse(
            {
                "items": [
                    {
                        "id": "UC-test-channel-legacy",
                        "snippet": {
                            "title": "Test Channel Legacy",
                            "description": "A test channel legacy",
                            "thumbnails": {"default": {"url": "https://example.com/thumb.jpg"}},
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr(youtube_oauth, "urlopen", fake_urlopen)

    response = TestClient(app).get(f"/youtube/auth/callback?code=abc&state={state}", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == youtube_upload_config.FRONTEND_DESTINATIONS_URL
    assert stored.get("YOUTUBE_REFRESH_TOKEN") == "refresh-token"

    dests = dest_service.list_destinations()
    assert any(d.channel_id == "UC-test-channel-legacy" for d in dests)


def test_oauth_callback_with_custom_return_url(monkeypatch):
    from app.services import destinations as dest_service

    state = "custom-return-state"
    custom_return = "https://custom-vercel-app.vercel.app/destinations"
    dest_service.store_oauth_state(state, return_url=custom_return)
    monkeypatch.setattr(youtube_oauth, "get_config_value", lambda name: f"{name}-value")

    def fake_urlopen(request, timeout):
        if request.data:
            return StubResponse(
                {
                    "access_token": "access-token-custom",
                    "refresh_token": "refresh-token-custom",
                    "scope": youtube_oauth.YOUTUBE_UPLOAD_SCOPE,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                }
            )
        return StubResponse(
            {
                "items": [
                    {
                        "id": "UC-custom-channel",
                        "snippet": {
                            "title": "Custom Channel",
                            "description": "Custom return channel",
                            "thumbnails": {"default": {"url": "https://example.com/custom.jpg"}},
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr(youtube_oauth, "urlopen", fake_urlopen)

    response = TestClient(app).get(f"/oauth/google/callback?code=abc&state={state}", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == custom_return


def test_google_oauth_callback_handles_google_error(monkeypatch):
    response = TestClient(app).get("/oauth/google/callback?error=access_denied", follow_redirects=False)

    assert response.status_code == 303
    assert "error=Google%20authorization%20denied" in response.headers["location"]


def test_google_oauth_callback_invalid_state(monkeypatch):
    response = TestClient(app).get("/oauth/google/callback?code=abc&state=bogus-state", follow_redirects=False)

    assert response.status_code == 303
    assert "error=Invalid%20OAuth%20state" in response.headers["location"]
