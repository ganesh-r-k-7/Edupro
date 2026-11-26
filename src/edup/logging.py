"""
logging.py — Centralized logging configuration for EduPro.

Supports both text (development) and JSON (production) formats.
Includes correlation ID support for request tracing.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from typing import Any


# Thread-local storage for correlation ID
_correlation_id = threading.local()


def get_correlation_id() -> str | None:
    """Get the current correlation ID from thread-local storage."""
    return getattr(_correlation_id, "correlation_id", None)


def set_correlation_id(correlation_id: str | None) -> None:
    """Set the correlation ID in thread-local storage."""
    if correlation_id is not None:
        _correlation_id.correlation_id = correlation_id
    elif hasattr(_correlation_id, "correlation_id"):
        delattr(_correlation_id, "correlation_id")


class CorrelationIdFilter(logging.Filter):
    """Filter to add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        correlation_id = get_correlation_id()
        if correlation_id:
            record.correlation_id = correlation_id
        else:
            record.correlation_id = "-"
        return True


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "-"),
        }

        # Add extra fields if present
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "name", "pathname", "process", "processName",
                "relativeCreated", "thread", "threadName", "exc_info",
                "exc_text", "stack_info", "correlation_id"
            }:
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def configure_logging(
    level: int = logging.INFO,
    stream: Any = None,
    json_format: bool = False,
    include_correlation_id: bool = True,
) -> None:
    """Configure root logger with standard or JSON format.

    Args:
        level: Logging level (default: INFO)
        stream: Output stream (default: sys.stdout)
        json_format: Use JSON format if True, text format if False
        include_correlation_id: Include correlation ID in logs
    """
    if stream is None:
        stream = sys.stdout

    # Prevent duplicate handlers
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(stream)
    handler.setLevel(level)

    if include_correlation_id:
        handler.addFilter(CorrelationIdFilter())

    if json_format:
        formatter: logging.Formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(correlation_id)s | %(message)s",
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
logger_api = get_logger("edup.api")