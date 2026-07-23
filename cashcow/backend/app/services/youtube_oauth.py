"""Google OAuth helpers for connecting YouTube channel destinations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import get_config_value, set_local_config_value, youtube_upload_config
from app.models.destination import Destination
from app.services import destinations

logger = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = youtube_upload_config.TOKEN_URI
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"
USERINFO_PROFILE_SCOPE = "https://www.googleapis.com/auth/userinfo.profile"
YOUTUBE_SCOPES = [YOUTUBE_UPLOAD_SCOPE, YOUTUBE_SCOPE, USERINFO_PROFILE_SCOPE]
REQUEST_TIMEOUT_SECONDS = 30
TOKEN_EXPIRY_SKEW_SECONDS = 60


class YouTubeOAuthError(RuntimeError):
    """Raised when a YouTube OAuth connection cannot be completed."""


@dataclass(frozen=True)
class OAuthTokenResponse:
    access_token: str
    refresh_token: str | None
    scope: str | None = None
    token_type: str | None = None
    expires_in: int | None = None

    @property
    def expires_at(self) -> datetime | None:
        if self.expires_in is None:
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=max(0, self.expires_in))


@dataclass(frozen=True)
class YouTubeChannelDetails:
    channel_id: str
    title: str
    thumbnail: str
    description: str


def authorization_url() -> str:
    client_id = _required_config("YOUTUBE_CLIENT_ID")
    state = secrets.token_urlsafe(24)
    destinations.store_oauth_state(state)
    logger.info("[oauth] authorization_url: state stored for pending OAuth callback")
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": youtube_upload_config.REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(YOUTUBE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
    )
    return f"{AUTH_URL}?{query}"


def exchange_code(code: str, state: str) -> OAuthTokenResponse:
    if not destinations.consume_oauth_state(state):
        raise YouTubeOAuthError("Invalid OAuth state")
    logger.info("[oauth] exchange_code: state consumed successfully")

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
        TOKEN_URI,
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


def connect_channel(code: str, state: str) -> Destination:
    tokens = exchange_code(code, state)
    if tokens.refresh_token is None:
        raise YouTubeOAuthError(
            "Google did not return a refresh token. Reconnect and approve offline access."
        )
    channel = fetch_channel_details(tokens.access_token)
    # Keep the legacy single-account refresh token populated for older code paths
    # and tests, but destination publishing never reads it.
    set_local_config_value("YOUTUBE_REFRESH_TOKEN", tokens.refresh_token)
    return destinations.upsert_connected_channel(
        channel_title=channel.title,
        channel_id=channel.channel_id,
        thumbnail=channel.thumbnail,
        description=channel.description,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_expires_at=tokens.expires_at,
    )


def fetch_channel_details(access_token: str) -> YouTubeChannelDetails:
    request = Request(
        CHANNELS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    response = _json_request(request)
    items = response.get("items")
    if not isinstance(items, list) or not items:
        raise YouTubeOAuthError("No YouTube channel was returned for this Google account")
    item = items[0]
    if not isinstance(item, dict):
        raise YouTubeOAuthError("YouTube channel endpoint returned an unexpected response")
    snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
    thumbnails = snippet.get("thumbnails") if isinstance(snippet.get("thumbnails"), dict) else {}
    thumbnail = ""
    for key in ("high", "medium", "default"):
        candidate = thumbnails.get(key)
        if isinstance(candidate, dict) and candidate.get("url"):
            thumbnail = str(candidate["url"])
            break
    channel_id = str(item.get("id") or "").strip()
    title = str(snippet.get("title") or "").strip()
    if not channel_id or not title:
        raise YouTubeOAuthError("YouTube channel response did not include id and title")
    return YouTubeChannelDetails(
        channel_id=channel_id,
        title=title,
        thumbnail=thumbnail,
        description=str(snippet.get("description") or ""),
    )


def refresh_access_token(destination_id: str, refresh_token: str) -> str:
    payload = urlencode(
        {
            "client_id": _required_config("YOUTUBE_CLIENT_ID"),
            "client_secret": _required_config("YOUTUBE_CLIENT_SECRET"),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    request = Request(
        TOKEN_URI,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        response = _json_request(request)
    except YouTubeOAuthError:
        destinations.mark_status(destination_id, "needs_reconnection")
        raise

    access_token = str(response.get("access_token") or "").strip()
    if not access_token:
        destinations.mark_status(destination_id, "needs_reconnection")
        raise YouTubeOAuthError("Refresh token response did not include an access token")
    expires_in = response.get("expires_in")
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if isinstance(expires_in, int)
        else None
    )
    destinations.update_tokens(destination_id, access_token=access_token, token_expires_at=expires_at)
    return access_token


def access_token_for_destination(destination_id: str) -> str:
    record = destinations.get_destination_record(destination_id)
    if record is None:
        raise YouTubeOAuthError("Destination not found")
    expires_at = record.destination.token_expires_at
    if expires_at is None:
        return record.access_token
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at > datetime.now(timezone.utc) + timedelta(seconds=TOKEN_EXPIRY_SKEW_SECONDS):
        return record.access_token
    return refresh_access_token(destination_id, record.refresh_token)


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
        value = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise YouTubeOAuthError("Google endpoint returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise YouTubeOAuthError("Google endpoint returned an unexpected response")
    return value


def _error_detail(exc: BaseException) -> str:
    if isinstance(exc, HTTPError):
        body = exc.read().decode("utf-8", errors="replace")
        return f"HTTP {exc.code}: {body or exc.reason}"
    return str(exc)

