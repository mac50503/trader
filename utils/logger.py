"""
utils/logger.py
---------------
Centralized logging setup.
All modules call get_logger(__name__) to get a properly configured logger.
Logs go to both console and a rotating file in /logs.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config

# Ensure logs directory exists
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def _setup_root_logger() -> None:
    global _initialized
    if _initialized:
        return

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root.addHandler(console)

    # Rotating file handler (5 MB per file, keep 3 backups)
    file_handler = RotatingFileHandler(
        LOGS_DIR / "trading_bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root.addHandler(file_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger. Call this at module level:
        logger = get_logger(__name__)
    """
    _setup_root_logger()
    return logging.getLogger(name)
