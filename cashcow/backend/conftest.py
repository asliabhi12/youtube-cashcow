"""Global Pytest fixtures for CashCow test suite environment isolation."""

from pathlib import Path
import pytest

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
