"""FastAPI application entry point.

Creates the app, enables CORS for the local Next.js frontend, and mounts
the API routers. Loaded by Uvicorn as `app.main:app`.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.presets import router as presets_router
from app.api.videos import router as videos_router
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
app.include_router(jobs_router)
app.include_router(presets_router)
app.include_router(videos_router)
