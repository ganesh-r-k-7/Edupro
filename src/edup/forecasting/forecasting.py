"""
forecasting.py — Forecasting utilities for EduPro.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# joblib is imported as a module-level variable so it can be patched in tests
try:
    import joblib
except ImportError:
    joblib = None

from edup.config import MODELS_DIR
from edup.exceptions import DataUnavailableError, ForecastError
from edup.logging import logger_forecasting
from edup.schema import validate_forecast_payload


def prepare_monthly_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to monthly total revenue for Prophet."""
    monthly = df.groupby(pd.Grouper(key="TransactionDate", freq="MS"))["Amount"].sum().reset_index()
    monthly.columns = ["ds", "y"]
    monthly = monthly[monthly["y"] > 0].reset_index(drop=True)
    logger_forecasting.debug("Prepared monthly revenue: %d months", len(monthly))
    return monthly


def prepare_monthly_enrollments(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly enrollment count."""
    monthly = (
        df.groupby(pd.Grouper(key="TransactionDate", freq="MS"))["TransactionID"]
        .count()
        .reset_index()
    )
    monthly.columns = ["ds", "y"]
    logger_forecasting.debug("Prepared monthly enrollments: %d months", len(monthly))
    return monthly


def prepare_category_revenue(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """Monthly revenue for a single course category."""
    sub = df[df["CourseCategory"] == category]
    monthly = (
        sub.groupby(pd.Grouper(key="TransactionDate", freq="MS"))["Amount"].sum().reset_index()
    )
    monthly.columns = ["ds", "y"]
    monthly = monthly[monthly["y"] >= 0].reset_index(drop=True)
    logger_forecasting.debug("Prepared category revenue for %s: %d months", category, len(monthly))
    return monthly


def forecast_with_prophet(
    series_df: pd.DataFrame, periods: int = 6, freq: str = "MS"
) -> tuple[Any, pd.DataFrame]:
    """Train Prophet model and generate future forecasts."""
    from prophet import Prophet

    logger_forecasting.info("Training Prophet model with %d data points", len(series_df))
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.05,
    )
    model.fit(series_df)

    future = model.make_future_dataframe(periods=periods, freq=freq)
    forecast = model.predict(future)
    logger_forecasting.info("Generated forecast for %d periods", periods)
    return model, forecast


# Allow patching joblib for testing
_joblib = joblib

# Sentinel for "no override provided"
_NO_OVERRIDE = object()


def load_forecast_results(
    _joblib_override: object = _NO_OVERRIDE, models_dir: Path | str | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """Load and validate forecast results.

    Returns (payload, error). A missing artifact is not an error; a corrupt or
    malformed artifact returns a user-facing error message.
    """
    # Use override for testing, otherwise use module-level joblib
    jl = _joblib if _joblib_override is _NO_OVERRIDE else _joblib_override
    if jl is None:
        logger_forecasting.error("joblib not available; cannot load forecast results")
        return None, "joblib is not installed; forecast results cannot be loaded."

    if models_dir is None:
        models_dir = MODELS_DIR
    models_dir = Path(models_dir)

    path = models_dir / "forecast_results.pkl"
    if not path.exists():
        logger_forecasting.warning("Forecast artifact not found at %s", path)
        return None, None

    try:
        logger_forecasting.info("Loading forecast artifact from %s", path)
        payload = jl.load(path)  # type: ignore[union-attr]
    except Exception as exc:
        logger_forecasting.error("Failed to load forecast artifact: %s", exc)
        return None, f"Forecast artifact could not be loaded: {type(exc).__name__}: {exc}"

    try:
        validate_forecast_payload(payload)
    except DataUnavailableError as exc:
        logger_forecasting.warning("Forecast artifact validation failed: %s", exc)
        return None, f"Forecast artifact is invalid: {exc}"

    logger_forecasting.info("Loaded forecast artifact successfully")
    return payload, None
