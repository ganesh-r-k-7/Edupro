"""
logging.py — Centralized logging configuration for EduPro.
"""

from __future__ import annotations

import logging
import sys
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def configure_logging(level: int = logging.INFO, stream: Any = None) -> None:
    """Configure root logger with a standard format.

    Args:
        level: Logging level (default: INFO)
        stream: Output stream (default: sys.stdout)
    """
    if stream is None:
        stream = sys.stdout

    # Prevent duplicate handlers
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.setLevel(level)
    root_logger.addHandler(handler)


# Module-level loggers for each subpackage
logger_config = get_logger("edup.config")
logger_data = get_logger("edup.data")
logger_features = get_logger("edup.features")
logger_analytics = get_logger("edup.analytics")
logger_models = get_logger("edup.models")
logger_forecasting = get_logger("edup.forecasting")
logger_reporting = get_logger("edup.reporting")
logger_schema = get_logger("edup.schema")
logger_app = get_logger("edup.app")