"""FastAPI Auth Router for CashCow.

Endpoints:
- POST /auth/login: Authenticate single admin user, return token and set HTTP-only cookie.
- POST /auth/logout: Logout user and clear session cookie.
- GET  /auth/me:    Return active session user info or 401 if unauthenticated.
"""

from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.auth.config import COOKIE_NAME, get_admin_username
from app.auth.security import (
    clear_failed_attempts,
    create_session_token,
    is_rate_limited,
    record_failed_attempt,
    verify_password,
    verify_session_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, description="Admin username")
    password: str = Field(min_length=1, description="Admin password")
    remember_me: bool = Field(default=False, description="Remember this device for 30 days")


class LoginResponse(BaseModel):
    status: str
    username: str
    expires_at: int
    token: str


class UserMeResponse(BaseModel):
    authenticated: bool
    username: str
    expires_at: int


def _extract_token(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> Optional[str]:
    """Extract session token from HttpOnly cookie or Authorization header."""
    # 1. Cookie
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token

    # 2. Authorization header: Bearer <token>
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    return None


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    """Authenticate single admin user and issue session token & cookie."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    admin_username = get_admin_username()

    if is_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 1 minute before retrying.",
        )

    if payload.username != admin_username or not verify_password(payload.password):
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Success: clear failed attempts for this IP
    clear_failed_attempts(client_ip)

    token, expires_at = create_session_token(payload.username, payload.remember_me)

    # Calculate cookie max-age in seconds
    max_age = 30 * 24 * 3600 if payload.remember_me else 24 * 3600

    # Detect HTTPS or Cloudflare Tunnel request for cross-site cookie support (Vercel)
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    samesite_attr = "none" if is_https else "lax"
    secure_attr = is_https

    # Set HTTP-only cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite=samesite_attr,
        secure=secure_attr,
        path="/",
    )

    return LoginResponse(
        status="ok",
        username=payload.username,
        expires_at=expires_at,
        token=token,
    )


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    """Clear session cookie and log out the user."""
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    samesite_attr = "none" if is_https else "lax"
    secure_attr = is_https

    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        samesite=samesite_attr,
        secure=secure_attr,
    )
    return {"status": "ok"}


@router.get("/me", response_model=UserMeResponse)
def get_me(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> UserMeResponse:
    """Return details of the current logged in session."""
    token = _extract_token(request, authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = verify_session_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    return UserMeResponse(
        authenticated=True,
        username=payload["sub"],
        expires_at=payload["exp"],
    )
