"""Global Pytest fixtures for CashCow test suite environment isolation."""

import sys
from pathlib import Path
import pytest

_BACKEND_DIR = Path(__file__).resolve().parent / "cashcow" / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import AppConfig, set_app_config
from app.core.environment import Environment
from app.infrastructure.database import init_database


@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path, monkeypatch):
    """Isolate pytest runs into temporary directories so tests never modify dev data."""
    test_config = AppConfig.load(env=Environment.TESTING, base_dir=tmp_path)
    set_app_config(test_config)

    # Initialize schema in isolated tmp_path database
    init_database()

    yield

    set_app_config(None)
