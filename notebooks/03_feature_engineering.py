"""
Notebook 03: Feature Engineering
EduPro Predictive Modeling Project

Creates advanced engineered features for ML models:
- Course features (PriceBand, DurationBucket, RatingTier, EncodedCourseLevel)
- Instructor features (ExperienceBucket, TeacherRatingScore, ExpertiseCategoryMatch)
- Historical performance features (EnrollmentCount, TotalRevenue, AverageRevenue, etc.)
- Time-based features (TransactionMonth, Quarter, Year, Seasonality)
"""

import os
import sys
from pathlib import Path

import pandas as pd

# Ensure shared package is importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from edup.config import PROCESSED_DATA_PATH, PROCESSED_DATA_PARQUET, ENGINEERED_COLUMNS
from edup.features import (
    price_band,
    duration_bucket,
    rating_tier,
    encode_course_level as _encode_course_level_fn,
    experience_bucket,
    teacher_rating_score,
    seasonality_label,
)


DATA_PATH = PROCESSED_DATA_PATH
OUTPUT_PATH = PROCESSED_DATA_PATH
OUTPUT_PARQUET = PROCESSED_DATA_PARQUET


def _derive_parquet_path(output_path: str) -> str:
    """Derive parquet path from output path."""
    return str(Path(output_path).with_suffix(".parquet"))


def _load_parquet_or_csv(path):
    """Load processed data from Parquet (preferred) or CSV (fallback)."""
    path = Path(path)
    parquet_path = path.with_suffix(".parquet")

    # Try Parquet first
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except Exception as exc:
            print(f"Warning: Failed to read Parquet file {parquet_path}: {exc}. Falling back to CSV.")
            # Fall through to CSV

    # Fall back to CSV
    if path.exists():
        return pd.read_csv(path, parse_dates=["TransactionDate"])

    raise FileNotFoundError(f"Processed data file not found: {path} (or {parquet_path})")


def load_data():
    df = _load_parquet_or_csv(DATA_PATH)
    print(f"Loaded: {df.shape}")
    return df


# --- Course Features ---

def add_price_band(df):
    """Bin CoursePrice into the canonical shared bands."""
    df['PriceBand'] = df['CoursePrice'].apply(price_band)
    return df


def add_duration_bucket(df):
    """Bucket CourseDuration using the canonical shared buckets."""
    df['DurationBucket'] = df['CourseDuration'].apply(duration_bucket)
    return df


def add_rating_tier(df):
    """Classify CourseRating into tiers."""
    df['RatingTier'] = df['CourseRating'].apply(rating_tier)
    return df


def _encode_course_level_col(df):
    """Ordinal encode CourseLevel."""
    df['EncodedCourseLevel'] = df['CourseLevel'].apply(_encode_course_level_fn).astype(int)
    return df


# Backward compatibility export for tests
encode_course_level = _encode_course_level_col


# --- Instructor Features ---

def add_experience_bucket(df):
    """Bucket teacher YearsOfExperience."""
    df['ExperienceBucket'] = df['YearsOfExperience'].apply(experience_bucket)
    return df


def add_teacher_rating_score(df):
    """Normalize TeacherRating with the fixed 1-5 scale used at inference."""
    df['TeacherRatingScore'] = df['TeacherRating'].apply(teacher_rating_score)
    return df


def add_expertise_category_match(df):
    """Flag whether teacher expertise aligns with course category."""
    df['ExpertiseCategoryMatch'] = (df['Expertise'] == df['CourseCategory']).astype(int)
    return df


# --- Time-Based Features ---

def add_time_features(df):
    """Extract temporal features from TransactionDate."""
    df['TransactionMonth'] = df['TransactionDate'].dt.month
    df['Quarter'] = df['TransactionDate'].dt.quarter
    df['Year'] = df['TransactionDate'].dt.year
    df['DayOfWeek'] = df['TransactionDate'].dt.dayofweek
    df['WeekOfYear'] = df['TransactionDate'].dt.isocalendar().week.astype(int)
    df['IsWeekend'] = (df['DayOfWeek'] >= 5).astype(int)
    df['SeasonalityLabel'] = df['Quarter'].apply(seasonality_label)
    return df


# --- Historical Performance Features ---

def add_historical_features(df):
    """Aggregate enrollment and revenue metrics per course."""
    course_stats = df.groupby('CourseID').agg(
        EnrollmentCount=('TransactionID', 'count'),
        TotalRevenue=('Amount', 'sum'),
        AverageRevenue=('Amount', 'mean'),
    ).reset_index()
    course_stats['RevenuePerEnrollment'] = (
        course_stats['TotalRevenue'] / course_stats['EnrollmentCount'].replace(0, 1)
    )
    df = df.merge(course_stats, on='CourseID', how='left')
    return df


def add_rolling_revenue(df):
    """Compute monthly rolling revenue and growth rate per course."""
    df_sorted = df.sort_values(['CourseID', 'TransactionDate'])

    monthly = df_sorted.groupby(['CourseID', 'Year', 'TransactionMonth'])['Amount'].sum().reset_index()
    monthly.rename(columns={'Amount': 'MonthlyRevenue'}, inplace=True)
    monthly = monthly.sort_values(['CourseID', 'Year', 'TransactionMonth'])
    monthly['RollingRevenueAverage'] = (
        monthly.groupby('CourseID')['MonthlyRevenue']
        .transform(lambda x: x.rolling(3, min_periods=1).mean())
    )
    monthly['RevenueGrowthRate'] = (
        monthly.groupby('CourseID')['MonthlyRevenue']
        .transform(lambda x: x.pct_change().fillna(0))
    )

    df = df.merge(monthly, on=['CourseID', 'Year', 'TransactionMonth'], how='left')
    df['MonthlyRevenueTrend'] = df['MonthlyRevenue']
    df['RollingRevenueAverage'] = df['RollingRevenueAverage'].fillna(0)
    df['RevenueGrowthRate'] = df['RevenueGrowthRate'].fillna(0)
    return df


def run_feature_engineering():
    """Execute complete feature engineering pipeline.

    Engineered columns are dropped first so rerunning the step does not create
    duplicate ``_x``/``_y`` columns. The output is written atomically to both CSV and Parquet.
    """
    df = load_data()
    df = df.drop(columns=[c for c in ENGINEERED_COLUMNS if c in df.columns])

    df = add_price_band(df)
    df = add_duration_bucket(df)
    df = add_rating_tier(df)
    df = encode_course_level(df)

    df = add_experience_bucket(df)
    df = add_teacher_rating_score(df)
    df = add_expertise_category_match(df)

    df = add_time_features(df)
    df = add_historical_features(df)
    df = add_rolling_revenue(df)

    # Write CSV (atomic)
    temp_path = f"{OUTPUT_PATH}.tmp"
    df.to_csv(temp_path, index=False)
    os.replace(temp_path, OUTPUT_PATH)

    # Write Parquet (atomic) - derive path from OUTPUT_PATH for testability
    parquet_path = _derive_parquet_path(OUTPUT_PATH)
    temp_parquet = f"{parquet_path}.tmp"
    df.to_parquet(temp_parquet, compression="zstd", index=False)
    os.replace(temp_parquet, parquet_path)

    print(f"Feature-engineered dataset saved: {OUTPUT_PATH} and {parquet_path}")
    print(f"Shape: {df.shape}")
    print(f"New columns: {[c for c in df.columns if c not in ['TransactionID','UserID','CourseID','TeacherID']]}")
    return df


if __name__ == '__main__':
    df = run_feature_engineering()