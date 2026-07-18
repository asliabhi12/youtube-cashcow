"""Application configuration.

Central place for values that main.py and the API layer read, so those
modules never carry hard-coded literals.
"""

from typing import Final

# Application version, surfaced by the /health endpoint.
VERSION: Final[str] = "0.1.0"

# Origins allowed to call this API. The Next.js dev server runs on port 3000.
CORS_ORIGINS: Final[list[str]] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
