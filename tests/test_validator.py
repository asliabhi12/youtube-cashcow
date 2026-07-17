"""Unit tests for system checks and directory validation utilities."""

import pytest
from src.validator import validate_python_version, validate_dependencies


def test_validate_python_version():
    """Verify that the python version check executes without error on minimum version (3.12+)."""
    # Should not raise any ValidationError in our target environment
    try:
        validate_python_version()
    except Exception as e:
        pytest.fail(f"Python version check failed unexpectedly: {e}")


def test_validate_dependencies():
    """Verify that dependencies check runs successfully when requirements are met."""
    try:
        validate_dependencies()
    except Exception as e:
        pytest.fail(f"Dependencies check failed unexpectedly: {e}")
