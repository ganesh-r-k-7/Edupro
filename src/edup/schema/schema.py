"""
schema.py — Data validation contracts for EduPro.

Provides validators for raw Excel sheets, processed data, and forecast payloads.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd

from edup.exceptions import DataContractError, DataUnavailableError


# ─── Sheet Schemas ─────────────────────────────────────────────────────────────

REQUIRED_SHEETS = ["Users", "Teachers", "Courses", "Transactions"]

SHEET_SCHEMAS = {
    "Users": {
        "required_columns": ["UserID", "UserName", "Age", "Gender", "Email"],
        "key": "UserID",
    },
    "Teachers": {
        "required_columns": [
            "TeacherID",
            "TeacherName",
            "Age",
            "Gender",
            "Expertise",
            "YearsOfExperience",
            "TeacherRating",
        ],
        "key": "TeacherID",
    },
    "Courses": {
        "required_columns": [
            "CourseID",
            "CourseName",
            "CourseCategory",
            "CourseType",
            "CourseLevel",
            "CoursePrice",
            "CourseDuration",
            "CourseRating",
        ],
        "key": "CourseID",
    },
    "Transactions": {
        "required_columns": [
            "TransactionID",
            "UserID",
            "CourseID",
            "TeacherID",
            "TransactionDate",
            "Amount",
            "PaymentMethod",
        ],
        "key": "TransactionID",
    },
}


def validate_sheet_sheets(xl: dict[str, pd.DataFrame]) -> None:
    """Validate that all required sheets exist."""
    missing = [s for s in REQUIRED_SHEETS if s not in xl]
    if missing:
        raise DataContractError(f"Missing required sheets: {missing}")


def validate_sheet_schema(df: pd.DataFrame, sheet_name: str) -> None:
    """Validate a single sheet against its schema."""
    schema = SHEET_SCHEMAS.get(sheet_name)
    if schema is None:
        raise DataContractError(f"No schema defined for sheet: {sheet_name}")

    missing_cols = [c for c in schema["required_columns"] if c not in df.columns]
    if missing_cols:
        raise DataContractError(
            f"Sheet '{sheet_name}' missing required columns: {missing_cols}"
        )

    key_col = schema["key"]
    if key_col in df.columns:
        dup_count = int(df[key_col].duplicated().sum())
        if dup_count:
            raise DataContractError(
                f"Sheet '{sheet_name}' key column '{key_col}' has {dup_count} duplicate(s)"
            )


def validate_sheet_schemas(xl: dict[str, pd.DataFrame]) -> None:
    """Validate all sheets in the workbook."""
    validate_sheet_sheets(xl)
    for sheet_name, df in xl.items():
        if sheet_name in SHEET_SCHEMAS:
            validate_sheet_schema(df, sheet_name)


# ─── Processed Data Contract ───────────────────────────────────────────────────

REQUIRED_DATA_COLUMNS = [
    "TransactionID",
    "TransactionDate",
    "UserID",
    "CourseID",
    "TeacherID",
    "CourseName",
    "CourseCategory",
    "CourseType",
    "CourseLevel",
    "CoursePrice",
    "CourseDuration",
    "CourseRating",
    "Amount",
    "PaymentMethod",
    "TeacherName",
    "TeacherRating",
    "YearsOfExperience",
]

REQUIRED_NUMERIC_COLUMNS = [
    "CoursePrice",
    "CourseDuration",
    "CourseRating",
    "Amount",
    "TeacherRating",
    "YearsOfExperience",
]

REQUIRED_TEXT_COLUMNS = [
    "TransactionID",
    "UserID",
    "CourseID",
    "TeacherID",
    "CourseName",
    "CourseCategory",
    "PaymentMethod",
    "TeacherName",
]

NON_NEGATIVE_NUMERIC_COLUMNS = ["Amount"]


def validate_processed_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the minimum dataset contract used by the dashboard and pipeline."""
    from edup.config import (
        COURSE_TYPES,
        COURSE_LEVELS,
        MIN_PRICE,
        MAX_PRICE,
        MIN_DURATION,
        MAX_DURATION,
        MIN_RATING,
        MAX_RATING,
        MIN_EXPERIENCE,
        MAX_EXPERIENCE,
    )

    if df is None or len(df) == 0:
        raise DataUnavailableError(
            "Processed data is empty. Run the preprocessing and feature-engineering steps."
        )

    missing = [c for c in REQUIRED_DATA_COLUMNS if c not in df.columns]
    if missing:
        raise DataUnavailableError(
            f"Processed data is missing required columns: {missing}."
        )

    if not pd.api.types.is_datetime64_any_dtype(df["TransactionDate"]):
        raise DataUnavailableError("TransactionDate must be parsed as a datetime column.")
    if df["TransactionDate"].isna().any():
        raise DataUnavailableError("TransactionDate contains unparseable or missing values.")

    invalid_types = set(df["CourseType"].dropna().unique()) - set(COURSE_TYPES)
    if invalid_types or df["CourseType"].isna().any():
        raise DataUnavailableError(
            f"CourseType must be one of {COURSE_TYPES}; found {sorted(invalid_types)}."
        )

    invalid_levels = set(df["CourseLevel"].dropna().unique()) - set(COURSE_LEVELS)
    if invalid_levels or df["CourseLevel"].isna().any():
        raise DataUnavailableError(
            f"CourseLevel must be one of {COURSE_LEVELS}; found {sorted(invalid_levels)}."
        )

    for column in REQUIRED_TEXT_COLUMNS:
        if df[column].isna().any():
            raise DataUnavailableError(f"{column} contains missing values.")

    duplicate_ids = int(df["TransactionID"].duplicated().sum())
    if duplicate_ids:
        raise DataUnavailableError(
            f"TransactionID contains {duplicate_ids} duplicate value(s); "
            "transaction IDs must be unique."
        )

    for column in REQUIRED_NUMERIC_COLUMNS:
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise DataUnavailableError(f"{column} must be numeric.")
        if df[column].isna().any():
            raise DataUnavailableError(f"{column} contains missing values.")
        if not np.isfinite(df[column].to_numpy(dtype=float)).all():
            raise DataUnavailableError(f"{column} contains non-finite values.")

    # Numeric bounds
    bounds_checks = [
        ("CoursePrice", MIN_PRICE, MAX_PRICE),
        ("CourseDuration", MIN_DURATION, MAX_DURATION),
        ("CourseRating", MIN_RATING, MAX_RATING),
        ("TeacherRating", MIN_RATING, MAX_RATING),
        ("YearsOfExperience", MIN_EXPERIENCE, MAX_EXPERIENCE),
    ]
    for column, minimum, maximum in bounds_checks:
        values = df[column].to_numpy(dtype=float)
        if ((values < minimum) | (values > maximum)).any():
            raise DataUnavailableError(
                f"{column} must be between {minimum:g} and {maximum:g}; "
                "found values outside that range."
            )

    for column in NON_NEGATIVE_NUMERIC_COLUMNS:
        if (df[column].to_numpy(dtype=float) < 0).any():
            raise DataUnavailableError(f"{column} cannot be negative.")

    return df


# ─── Forecast Payload Contract ─────────────────────────────────────────────────

FORECAST_REQUIRED_COLUMNS = ["ds", "yhat", "yhat_lower", "yhat_upper"]


def validate_forecast_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the cached forecast payload consumed by the dashboard."""
    if not isinstance(payload, dict):
        raise DataUnavailableError("Forecast payload must be a dictionary.")

    revenue = payload.get("revenue")
    if revenue is None:
        raise DataUnavailableError("Forecast payload is missing the revenue forecast.")
    if not isinstance(revenue, pd.DataFrame) or revenue.empty:
        raise DataUnavailableError("Revenue forecast must be a non-empty DataFrame.")

    missing = [c for c in FORECAST_REQUIRED_COLUMNS if c not in revenue.columns]
    if missing:
        raise DataUnavailableError(f"Revenue forecast is missing columns: {missing}.")

    dates = pd.to_datetime(revenue["ds"], errors="coerce", format="mixed")
    if not pd.api.types.is_datetime64_any_dtype(dates):
        raise DataUnavailableError("Revenue forecast dates could not be normalized.")
    if getattr(dates.dt, "tz", None) is not None:
        dates = dates.dt.tz_convert(None)
    if dates.isna().any():
        raise DataUnavailableError("Revenue forecast contains invalid dates.")

    revenue = revenue.copy()
    revenue["ds"] = dates

    for column in ["yhat", "yhat_lower", "yhat_upper"]:
        if not pd.api.types.is_numeric_dtype(revenue[column]):
            raise DataUnavailableError(f"Revenue forecast column {column} must be numeric.")
        if not np.isfinite(revenue[column].to_numpy(dtype=float)).all():
            raise DataUnavailableError(f"Revenue forecast column {column} contains non-finite values.")

    payload["revenue"] = revenue
    return payload