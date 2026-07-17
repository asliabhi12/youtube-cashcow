"""Utility helper functions for paths, timestamps, permissions, and file checks.

These helpers support common filesystem operations, validation, and platform checks.
"""

from datetime import datetime
import os
from pathlib import Path
import sys
from typing import Union

from src.exceptions import FolderError


def resolve_path(path: Union[str, Path]) -> Path:
    """Resolve a path to an absolute path, handling user home expansion.

    Args:
        path: The path as a string or Path object.

    Returns:
        Path: The absolute resolved Path object.
    """
    return Path(path).expanduser().resolve()


def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure a directory exists, creating it and parent directories if missing.

    Args:
        path: The target directory path.

    Returns:
        Path: The resolved absolute directory path.

    Raises:
        FolderError: If directory creation fails or path is a file.
    """
    resolved_path = resolve_path(path)
    if resolved_path.exists() and not resolved_path.is_dir():
        raise FolderError(
            f"Cannot create directory '{resolved_path}' because a file with the same name exists."
        )

    try:
        resolved_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise FolderError(
            f"Failed to create directory '{resolved_path}': {str(e)}"
        ) from e

    return resolved_path


def check_write_permission(path: Union[str, Path]) -> bool:
    """Check if the application has write permissions for a given directory or file.

    Args:
        path: The path to check.

    Returns:
        bool: True if write permission is granted, False otherwise.
    """
    resolved = resolve_path(path)
    if not resolved.exists():
        # If it doesn't exist, we check if we can write to the parent directory
        parent = resolved.parent
        return os.access(parent, os.W_OK)
    return os.access(resolved, os.W_OK)


def check_read_permission(path: Union[str, Path]) -> bool:
    """Check if the application has read permissions for a given directory or file.

    Args:
        path: The path to check.

    Returns:
        bool: True if read permission is granted, False otherwise.
    """
    resolved = resolve_path(path)
    if not resolved.exists():
        return os.access(resolved.parent, os.R_OK)
    return os.access(resolved, os.R_OK)


def get_current_timestamp(format_str: str = "%Y-%m-%d_%H-%M-%S") -> str:
    """Generate a formatted timestamp string.

    Args:
        format_str: The datetime format string. Defaults to filename-friendly format.

    Returns:
        str: The formatted current timestamp.
    """
    return datetime.now().strftime(format_str)


def get_current_date() -> str:
    """Generate a standard daily date string (YYYY-MM-DD) for log naming.

    Returns:
        str: The date string.
    """
    return datetime.now().strftime("%Y-%m-%d")


def check_python_version(required_min: tuple[int, int]) -> bool:
    """Check if the current Python version meets the required minimum.

    Args:
        required_min: A tuple (major, minor) representing minimum version.

    Returns:
        bool: True if meeting requirements, False otherwise.
    """
    return sys.version_info[:2] >= required_min
