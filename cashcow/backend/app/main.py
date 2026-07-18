"""FastAPI application entry point.

Creates the app, enables CORS for the local Next.js frontend, and mounts
the API routers. Loaded by Uvicorn as `app.main:app`.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import CORS_ORIGINS, VERSION

app = FastAPI(title="CashCow", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
