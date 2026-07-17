"""System validation engine for YouTube CashCow.

Performs startup checks including Python version, package dependencies,
configuration integrity, folder existence, and write permissions.
"""

import importlib
from pathlib import Path

from src.config import Settings
from src.constants import MIN_PYTHON_VERSION, REQUIRED_DIRECTORIES
from src.exceptions import DependencyError, FolderError, ValidationError
from src.utils import (
    check_python_version,
    check_read_permission,
    check_write_permission,
    ensure_directory,
    resolve_path,
)


def validate_python_version() -> None:
    """Validate that the system meets the minimum Python version requirements.

    Raises:
        ValidationError: If the running Python version is less than 3.12.
    """
    if not check_python_version(MIN_PYTHON_VERSION):
        import sys
        current_version = ".".join(map(str, sys.version_info[:3]))
        req_version = ".".join(map(str, MIN_PYTHON_VERSION))
        raise ValidationError(
            f"Python version check failed: Found Python {current_version}, "
            f"but {req_version}+ is required."
        )


def validate_dependencies() -> None:
    """Validate that all core dependencies are installed and importable.

    Raises:
        DependencyError: If a required library cannot be imported.
    """
    required_packages = [
        ("pydantic", "pydantic"),
        ("yaml", "PyYAML"),
        ("typer", "Typer"),
        ("rich", "Rich"),
        ("dotenv", "python-dotenv"),
    ]

    missing_packages = []
    for module_name, package_name in required_packages:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing_packages.append(package_name)

    if missing_packages:
        raise DependencyError(
            f"Missing required Python dependencies: {', '.join(missing_packages)}. "
            f"Please run 'pip install -r requirements.txt' to install them."
        )


def initialize_directories(settings: Settings) -> None:
    """Automatically create all configured and default directories if they do not exist.

    Args:
        settings: The validated application configuration.

    Raises:
        FolderError: If directories cannot be created.
    """
    # Collect directories from config
    directories_to_create = [
        settings.storage.download_dir,
        settings.storage.temp_dir,
        settings.storage.output_dir,
        settings.storage.assets_dir,
        settings.logging.log_dir,
        # Create nested assets directories too
        f"{settings.storage.assets_dir}/overlays",
        f"{settings.storage.assets_dir}/logos",
        f"{settings.storage.assets_dir}/masks",
        f"{settings.storage.assets_dir}/intro",
        f"{settings.storage.assets_dir}/outro",
    ]

    for dir_path in directories_to_create:
        try:
            ensure_directory(dir_path)
        except FolderError as e:
            raise FolderError(
                f"Initialization failed: Could not create folder structure '{dir_path}'. {e}"
            ) from e


def validate_directories(settings: Settings) -> None:
    """Verify that all folders exist and have correct read/write permissions.

    Args:
        settings: The validated application configuration.

    Raises:
        FolderError: If folders are missing, are not directories, or lack
                     required read/write access.
    """
    directories_to_check = [
        ("download_dir", settings.storage.download_dir),
        ("temp_dir", settings.storage.temp_dir),
        ("output_dir", settings.storage.output_dir),
        ("assets_dir", settings.storage.assets_dir),
        ("log_dir", settings.logging.log_dir),
    ]

    for key, dir_str in directories_to_check:
        path = resolve_path(dir_str)
        
        # 1. Existence and Directory type checks
        if not path.exists():
            raise FolderError(
                f"Directory check failed: '{path}' ({key}) does not exist. "
                f"Please run initialization or check storage config."
            )
        if not path.is_dir():
            raise FolderError(
                f"Directory check failed: '{path}' ({key}) exists but is not a directory."
            )
        
        # 2. Permissions check
        if not check_read_permission(path):
            raise FolderError(
                f"Permission check failed: Read access denied for directory '{path}' ({key})."
            )
        if not check_write_permission(path):
            raise FolderError(
                f"Permission check failed: Write access denied for directory '{path}' ({key})."
            )


def validate_full_system(settings: Settings) -> None:
    """Perform a complete end-to-end environment, code dependency, and storage validation.

    Args:
        settings: The validated application configuration.

    Raises:
        ValidationError, DependencyError, FolderError: If any validation checks fail.
    """
    validate_python_version()
    validate_dependencies()
    validate_directories(settings)

