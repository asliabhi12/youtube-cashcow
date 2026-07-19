"""Minimal YouTube OAuth helpers for connecting one upload account."""

from __future__ import annotations

from dataclasses import dataclass
import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import get_config_value, set_local_config_value, youtube_upload_config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
REQUEST_TIMEOUT_SECONDS = 30


class YouTubeOAuthError(RuntimeError):
    """Raised when the MVP YouTube OAuth connection cannot be completed."""


@dataclass(frozen=True)
class OAuthTokenResponse:
    access_token: str
    refresh_token: str | None
    scope: str | None = None
    token_type: str | None = None
    expires_in: int | None = None


_pending_states: set[str] = set()


def authorization_url() -> str:
    client_id = _required_config("YOUTUBE_CLIENT_ID")
    state = secrets.token_urlsafe(24)
    _pending_states.add(state)
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": youtube_upload_config.REDIRECT_URI,
            "response_type": "code",
            "scope": YOUTUBE_UPLOAD_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
    )
    return f"{AUTH_URL}?{query}"


def exchange_code(code: str, state: str) -> OAuthTokenResponse:
    if state not in _pending_states:
        raise YouTubeOAuthError("Invalid OAuth state")
    _pending_states.remove(state)

    payload = urlencode(
        {
            "client_id": _required_config("YOUTUBE_CLIENT_ID"),
            "client_secret": _required_config("YOUTUBE_CLIENT_SECRET"),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": youtube_upload_config.REDIRECT_URI,
        }
    ).encode("utf-8")
    request = Request(
        youtube_upload_config.TOKEN_URI,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    response = _json_request(request)
    access_token = str(response.get("access_token") or "").strip()
    refresh_token = str(response.get("refresh_token") or "").strip() or None
    if not access_token:
        raise YouTubeOAuthError("OAuth token response did not include an access token")
    if refresh_token is not None:
        set_local_config_value("YOUTUBE_REFRESH_TOKEN", refresh_token)
    return OAuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        scope=response.get("scope"),
        token_type=response.get("token_type"),
        expires_in=response.get("expires_in"),
    )


def _required_config(name: str) -> str:
    value = get_config_value(name)
    if not value:
        raise YouTubeOAuthError(f"{name} is not configured")
    return value


def _json_request(request: Request) -> dict:
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise YouTubeOAuthError(_error_detail(exc)) from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise YouTubeOAuthError("OAuth token endpoint returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise YouTubeOAuthError("OAuth token endpoint returned an unexpected response")
    return value


def _error_detail(exc: BaseException) -> str:
    if isinstance(exc, HTTPError):
        body = exc.read().decode("utf-8", errors="replace")
        return f"HTTP {exc.code}: {body or exc.reason}"
    return str(exc)
