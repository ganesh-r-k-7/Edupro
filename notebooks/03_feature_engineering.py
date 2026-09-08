"""
Notebook 03: Feature Engineering
EduPro Predictive Modeling Project

Creates advanced engineered features for ML models:
- Course features (PriceBand, DurationBucket, RatingTier, EncodedCourseLevel)
- Instructor features (ExperienceBucket, TeacherRatingScore, ExpertiseCategoryMatch)
- Historical performance features (EnrollmentCount, TotalRevenue, AverageRevenue, etc.)
- Time-based features (TransactionMonth, Quarter, Year, Seasonality)
"""

import pandas as pd
import numpy as np
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed_data.csv')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed_data.csv')


def load_data():
    df = pd.read_csv(DATA_PATH, parse_dates=['TransactionDate'])
    print(f"Loaded: {df.shape}")
    return df


# --- Course Features ---

def add_price_band(df):
    """Bin CoursePrice into descriptive bands."""
    bins = [-0.01, 0, 50, 100, 200, 500]
    labels = ['Free', 'Budget', 'Standard', 'Premium', 'Elite']
    df['PriceBand'] = pd.cut(df['CoursePrice'], bins=bins, labels=labels)
    df['PriceBand'] = df['PriceBand'].astype(str)
    return df


def add_duration_bucket(df):
    """Bucket CourseDuration into short/medium/long segments."""
    bins = [0, 10, 25, 50, 200]
    labels = ['Short', 'Medium', 'Long', 'Extended']
    df['DurationBucket'] = pd.cut(df['CourseDuration'], bins=bins, labels=labels)
    df['DurationBucket'] = df['DurationBucket'].astype(str)
    return df


def add_rating_tier(df):
    """Classify CourseRating into tiers."""
    def tier(r):
        if r >= 4.5:
            return 'Elite'
        elif r >= 4.0:
            return 'High'
        elif r >= 3.0:
            return 'Medium'
        else:
            return 'Low'
    df['RatingTier'] = df['CourseRating'].apply(tier)
    return df


def encode_course_level(df):
    """Ordinal encode CourseLevel."""
    level_map = {'Beginner': 1, 'Intermediate': 2, 'Advanced': 3}
    df['EncodedCourseLevel'] = df['CourseLevel'].map(level_map).fillna(1).astype(int)
    return df


# --- Instructor Features ---

def add_experience_bucket(df):
    """Bucket teacher YearsOfExperience."""
    bins = [-1, 2, 5, 10, 50]
    labels = ['Junior', 'Mid', 'Senior', 'Expert']
    df['ExperienceBucket'] = pd.cut(df['YearsOfExperience'], bins=bins, labels=labels)
    df['ExperienceBucket'] = df['ExperienceBucket'].astype(str)
    return df


def add_teacher_rating_score(df):
    """Normalize TeacherRating to 0-1 scale."""
    min_r = df['TeacherRating'].min()
    max_r = df['TeacherRating'].max()
    df['TeacherRatingScore'] = (df['TeacherRating'] - min_r) / (max_r - min_r + 1e-9)
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

    # Seasonality: Q1=Jan-Mar (New Year rush), Q3=Jul-Sep (summer), Q4=Oct-Dec (year-end)
    def seasonality(q):
        if q == 1:
            return 'NewYearRush'
        elif q == 2:
            return 'Spring'
        elif q == 3:
            return 'Summer'
        else:
            return 'YearEnd'
    df['SeasonalityLabel'] = df['Quarter'].apply(seasonality)
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
    """Execute complete feature engineering pipeline."""
    df = load_data()

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

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Feature-engineered dataset saved: {OUTPUT_PATH}")
    print(f"Shape: {df.shape}")
    print(f"New columns: {[c for c in df.columns if c not in ['TransactionID','UserID','CourseID','TeacherID']]}")
    return df


if __name__ == '__main__':
    df = run_feature_engineering()
