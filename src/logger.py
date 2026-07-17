"""Centralized logging system for YouTube CashCow.

Implements colored console logs using Rich and daily rotating file logs.
All modules should obtain loggers using `logging.getLogger("youtube_cashcow.module_name")`.
"""

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Union

from rich.logging import RichHandler

from src.constants import APP_NAME, DEFAULT_LOG_LEVEL
from src.utils import ensure_directory


def get_logger(name: str = "youtube_cashcow") -> logging.Logger:
    """Retrieve a logger instance.

    Args:
        name: The name of the logger. Defaults to 'youtube_cashcow'.

    Returns:
        logging.Logger: The logger instance.
    """
    return logging.getLogger(name)


def init_logger(
    level: str = DEFAULT_LOG_LEVEL,
    log_dir: Union[str, Path] = "logs",
    debug_mode: bool = False,
) -> logging.Logger:
    """Initialize the global logger with console (Rich) and rotating file handlers.

    Args:
        level: Default log level (e.g., 'DEBUG', 'INFO').
        log_dir: Directory where log files will be saved.
        debug_mode: If True, overrides level to DEBUG.

    Returns:
        logging.Logger: The configured root-level application logger.
    """
    # Create the parent logger
    logger = logging.getLogger("youtube_cashcow")
    
    # Reset existing handlers if already initialized (prevents double logging)
    if logger.handlers:
        logger.handlers.clear()

    # Determine log level
    log_level = logging.DEBUG if debug_mode else getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    logger.propagate = False  # Avoid duplicating to system root logger

    # 1. Console Handler (Rich)
    console_handler = RichHandler(
        level=log_level,
        rich_tracebacks=True,
        markup=True,
        omit_repeated_times=False,
    )
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 2. File Handler (Timed Rotating: rotates daily)
    try:
        log_path = ensure_directory(log_dir)
        # File name format: youtube_cashcow.log, rotated daily
        file_name = log_path / "youtube_cashcow.log"
        
        file_handler = TimedRotatingFileHandler(
            filename=file_name,
            when="midnight",
            interval=1,
            backupCount=30,  # Keep 30 days of logs
            encoding="utf-8",
        )
        
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Fallback if log directory is unwritable
        logger.warning(
            f"Could not initialize file logging due to FolderError: {e}. "
            f"Logging to console only."
        )

    return logger
