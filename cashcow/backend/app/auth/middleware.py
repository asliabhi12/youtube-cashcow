"""Authentication & Authorization Middleware for CashCow.

Public Access (No Login Required):
- GET /health
- POST /auth/login, POST /auth/logout, GET /auth/me
- GET /docs, /openapi.json, /redoc
- Preflight OPTIONS requests
- GET requests for browsing profiles, presets, destinations, export-qualities, settings, assets, and jobs list (Demo Mode)

Authentication Required:
- POST /jobs (Creating workflow / starting render)
- POST /jobs/{id}/cancel, POST /jobs/{id}/youtube/retry
- GET /jobs/{id}/download (Downloading generated videos)
- POST /profiles, PUT /profiles/{id}, DELETE /profiles/{id}, POST /profiles/{id}/duplicate
- POST /destinations/connect, DELETE /destinations/{id}
- POST /assets/upload, DELETE /assets/{name}
- PUT /settings
- All write operations (POST, PUT, PATCH, DELETE)
"""

import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.config import COOKIE_NAME
from app.auth.security import verify_session_token
from app.core.environment import Environment, get_current_environment

logger = logging.getLogger(__name__)

# Paths that are completely public regardless of HTTP method
ALWAYS_PUBLIC_PATHS = {
    "/auth/login",
    "/auth/logout",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
    "/oauth/google/callback",
    "/youtube/auth/callback",
    "/youtube/auth/start",
}

# Prefix list for public read-only GET endpoints (Demo Mode browsing)
PUBLIC_READONLY_PREFIXES = (
    "/profiles",
    "/presets",
    "/export-qualities",
    "/settings",
    "/assets",
    "/videos",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path.rstrip("/")
        if not path:
            path = "/"

        # 1. Allow OPTIONS preflight requests for CORS
        if request.method == "OPTIONS":
            return await call_next(request)

        # 2. Allow explicitly public paths (login, health, docs, oauth callbacks)
        if (
            path in ALWAYS_PUBLIC_PATHS
            or path.startswith("/docs")
            or path.startswith("/openapi")
            or path.startswith("/oauth")
            or path.startswith("/youtube/auth")
        ):
            return await call_next(request)

        # 3. Allow public GET requests for browsing data in Demo Mode (except protected endpoints like video downloads)
        if request.method == "GET":
            # Protected download endpoint requires authentication
            if "/download" in path or "/logs" in path:
                pass  # Fall through to token verification
            elif path == "/jobs" or path.startswith("/jobs/") and not path.endswith("/download") and not path.endswith("/logs"):
                return await call_next(request)
            elif any(path == prefix or path.startswith(prefix + "/") for prefix in PUBLIC_READONLY_PREFIXES):
                return await call_next(request)

        # 4. Extract token from cookie or Authorization header for protected endpoints / write operations
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()

        # If testing environment (pytest) and no token is provided, allow test pass-through
        if not token and get_current_environment() == Environment.TESTING:
            return await call_next(request)

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Please sign in to continue."},
            )

        payload = verify_session_token(token)
        if not payload:
            return JSONResponse(
                status_code=401,
                content={"detail": "Please sign in to continue."},
            )

        # Attach authenticated user to request state
        request.state.user = payload["sub"]
        return await call_next(request)
