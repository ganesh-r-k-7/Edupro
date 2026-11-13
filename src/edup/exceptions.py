"""
exceptions.py — Custom exceptions for EduPro.
"""

from __future__ import annotations


class DataContractError(ValueError):
    """Raised when a data contract validation fails."""

    pass


class DataUnavailableError(DataContractError):
    """Raised when the processed dataset is missing or violates its contract."""

    pass


class ModelLoadError(Exception):
    """Raised when a model artifact cannot be loaded."""

    pass


class ForecastError(DataContractError):
    """Raised when forecast operations fail."""

    pass


class DashboardError(Exception):
    """Raised when dashboard initialization fails."""

    pass
