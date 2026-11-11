"""
data.py — Data loading and preprocessing for EduPro.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import pandas as pd

from edup.config import RAW_DATA_PATH, PROCESSED_DATA_PATH
from edup.schema import validate_processed_data, validate_sheet_schemas
from edup.exceptions import DataContractError, DataUnavailableError


def load_raw_data(path: Path | str | None = None) -> dict[str, pd.DataFrame]:
    """Load all sheets from the Excel workbook."""
    path = path or RAW_DATA_PATH
    if not os.path.exists(path):
        raise DataUnavailableError(f"Raw data file not found: {path}")
    xl = pd.read_excel(path, sheet_name=None)
    validate_sheet_schemas(xl)
    return xl


def preprocess_data(xl: dict[str, pd.DataFrame] | None = None, output_path: Path | str | None = None) -> pd.DataFrame:
    """Run the full preprocessing pipeline."""
    if xl is None:
        xl = load_raw_data()

    users = xl["Users"]
    teachers = xl["Teachers"]
    courses = xl["Courses"]
    transactions = xl["Transactions"]

    # Merge
    df = transactions.merge(courses, on="CourseID", how="left")
    df = df.merge(teachers, on="TeacherID", how="left")
    df = df.merge(users[["UserID", "Age", "Gender"]], on="UserID", how="left")
    df.rename(
        columns={
            "Age_x": "UserAge",
            "Age_y": "TeacherAge",
            "Gender_x": "UserGender",
            "Gender_y": "TeacherGender",
        },
        inplace=True,
    )

    # Remove duplicates
    df = df.drop_duplicates().reset_index(drop=True)

    # Fix datatypes
    df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])
    df["CoursePrice"] = pd.to_numeric(df["CoursePrice"], errors="coerce").fillna(0)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0)
    df["CourseDuration"] = pd.to_numeric(df["CourseDuration"], errors="coerce").fillna(0)
    df["CourseRating"] = pd.to_numeric(df["CourseRating"], errors="coerce").fillna(df["CourseRating"].mean() if "CourseRating" in df else 0)
    df["TeacherRating"] = pd.to_numeric(df["TeacherRating"], errors="coerce").fillna(df["TeacherRating"].mean() if "TeacherRating" in df else 0)
    df["YearsOfExperience"] = pd.to_numeric(df["YearsOfExperience"], errors="coerce").fillna(0).astype(int)

    # Handle missing values
    numeric_cols = df.select_dtypes(include=["number"]).columns
    for col in numeric_cols:
        if df[col].isnull().sum() > 0:
            df[col].fillna(df[col].median(), inplace=True)

    categorical_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in categorical_cols:
        if df[col].isnull().sum() > 0:
            df[col].fillna(df[col].mode()[0], inplace=True)

    # Validate and save
    validate_processed_data(df)

    output_path = output_path or PROCESSED_DATA_PATH
    temp_path = f"{output_path}.tmp"
    df.to_csv(temp_path, index=False)
    os.replace(temp_path, output_path)

    return df


def load_processed_data(path: Path | str | None = None) -> pd.DataFrame:
    """Load and validate the feature-engineered dataset."""
    path = path or PROCESSED_DATA_PATH
    if not os.path.exists(path):
        raise DataUnavailableError(
            f"Processed data file not found: {path}. "
            "Run the preprocessing and feature-engineering steps."
        )
    try:
        df = pd.read_csv(path, parse_dates=["TransactionDate"])
    except pd.errors.EmptyDataError as exc:
        raise DataUnavailableError(f"Processed data file is empty: {path}.") from exc
    except (pd.errors.ParserError, ValueError, OSError) as exc:
        raise DataUnavailableError(
            f"Processed data could not be read from {path}: {exc}"
        ) from exc

    return validate_processed_data(df)