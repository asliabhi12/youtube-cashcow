"""FastAPI application entry point.

Creates the app, enables CORS for the local Next.js frontend, and mounts
the API routers. Loaded by Uvicorn as `app.main:app`.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assets import router as assets_router
from app.api.destinations import router as destinations_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.metadata import router as metadata_router
from app.api.presets import router as presets_router
from app.api.profiles import router as profiles_router
from app.api.videos import router as videos_router
from app.api.oauth import router as oauth_router
from app.api.youtube import router as youtube_router
from app.core.config import CORS_ORIGINS, VERSION
from app.services.ai.provider_factory import (
    metadata_generation_configured,
    metadata_provider_name,
)

from app.services.workflow import resume_unfinished_jobs  # noqa: E402

logger = logging.getLogger(__name__)


def validate_metadata_configuration() -> None:
    """Log metadata provider state without blocking application startup."""
    provider = metadata_provider_name()
    logger.info("AI metadata provider active: %s", provider)
    if not metadata_generation_configured():
        logger.warning(
            "GEMINI_API_KEY is not configured; AI metadata generation is disabled."
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    validate_metadata_configuration()
    unfinished = resume_unfinished_jobs()
    if unfinished:
        logger.info("Resumed %d unfinished job(s) from agent memory: %s", len(unfinished), unfinished)
    yield


app = FastAPI(title="CashCow", version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assets_router)
app.include_router(destinations_router)
app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(metadata_router)
app.include_router(presets_router)
app.include_router(profiles_router)
app.include_router(videos_router)
app.include_router(oauth_router)
app.include_router(youtube_router)
