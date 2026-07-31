"""Unit tests verifying CORS header emission across deployment environments."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_cors_vercel_origin_returns_allow_origin_and_credentials():
    """Verify requests from Vercel origins receive Access-Control-Allow-Origin."""
    origin = "https://cashcow-frontend-app.vercel.app"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_options_preflight_vercel_origin():
    """Verify OPTIONS preflight requests from Vercel origins succeed with CORS headers."""
    origin = "https://cashcow-frontend-app.vercel.app"
    response = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_cors_cloudflare_tunnel_origin():
    """Verify requests from Cloudflare Tunnel origins receive Access-Control-Allow-Origin."""
    origin = "https://scripts-rail-chapel-income.trycloudflare.com"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_localhost_origin():
    """Verify requests from localhost origins continue working."""
    origin = "http://localhost:3000"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
