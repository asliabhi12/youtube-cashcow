"""Response schema for the health endpoint."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Shape of the GET /health payload."""

    status: str
    version: str
