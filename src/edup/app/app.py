"""
app.py — Streamlit dashboard utilities for EduPro.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import pandas as pd

from edup.config import PROCESSED_DATA_PATH
from edup.data import load_processed_data
from edup.models import load_enrollment_model
from edup.forecasting import load_forecast_results
from edup.exceptions import DataUnavailableError, ModelLoadError, ForecastError, DashboardError


def validate_dashboard_artifacts() -> Tuple[pd.DataFrame | None, str | None]:
    """Validate that all required artifacts exist for the dashboard."""
    errors = []

    # Check processed data
    if not os.path.exists(PROCESSED_DATA_PATH):
        errors.append(f"Processed data not found: {PROCESSED_DATA_PATH}")

    # Check forecast (optional)
    forecast_path = Path("models") / "forecast_results.pkl"
    if not os.path.exists(forecast_path):
        errors.append("Forecast results not found (run notebooks/06_forecasting.py)")

    if errors:
        return None, "; ".join(errors)

    return None, None


def load_dashboard_data() -> Tuple[pd.DataFrame | None, str | None]:
    """Load and validate all data needed for the dashboard."""
    try:
        df = load_processed_data()
        return df, None
    except DataUnavailableError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"Failed to load dashboard data: {exc}"