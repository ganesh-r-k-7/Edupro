"""
feature_contract.py — Canonical course-configuration features for EduPro.

This module is the single source of truth for inference and training
preprocessing. It intentionally excludes transaction-only fields
(PaymentMethod, TransactionMonth, Quarter, IsWeekend, SeasonalityLabel)
from the course-level model schema. PaymentMethod remains an informational
input in the dashboard, not a demand feature.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

COURSE_CATEGORIES = [
    'Programming', 'Design', 'Business', 'Marketing', 'Data Science',
    'Machine Learning', 'Cybersecurity', 'Project Management', 'Finance',
    'Artificial Intelligence', 'Web Development', 'Digital Marketing',
]
COURSE_LEVELS = ['Beginner', 'Intermediate', 'Advanced']
COURSE_TYPES = ['Paid', 'Free']
PAYMENT_METHODS = ['Credit Card', 'PayPal', 'Bank Transfer']
PRICE_BANDS = ['Free', 'Budget', 'Standard', 'Premium', 'Elite']
DURATION_BUCKETS = ['Short', 'Medium', 'Long', 'Extended']
RATING_TIERS = ['Low', 'Medium', 'High', 'Elite']
EXPERIENCE_BUCKETS = ['Junior', 'Mid', 'Senior', 'Expert']
SEASONALITY_LABELS = ['NewYearRush', 'Spring', 'Summer', 'YearEnd']

MAX_PRICE = 500.0
MIN_PRICE = 0.0
MAX_DURATION = 200.0
MIN_DURATION = 1.0
MIN_RATING = 1.0
MAX_RATING = 5.0
MIN_EXPERIENCE = 0
MAX_EXPERIENCE = 30

# Canonical bins. They match pd.cut(right=True) on the engineered dataset:
# 0 -> Free, 50 -> Budget, 100 -> Standard, 200 -> Premium, 500 -> Elite.
PRICE_BAND_EDGES = [0.0, 50.0, 100.0, 200.0, 500.0]
DURATION_BUCKET_EDGES = [0.0, 10.0, 25.0, 50.0, 200.0]

NUMERIC_FEATURES = [
    'CoursePrice', 'CourseDuration', 'CourseRating',
    'TeacherRating', 'YearsOfExperience', 'EncodedCourseLevel',
    'TeacherRatingScore',
]
CATEGORICAL_FEATURES = [
    'CourseCategory', 'CourseType', 'PriceBand',
    'DurationBucket', 'RatingTier', 'ExperienceBucket',
]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Explicitly excluded from the course-level schema because they are
# transaction-level, unknown at course-design time, or arbitrarily
# aggregated in the legacy course-level dataset.
EXCLUDED_TRANSACTION_FEATURES = [
    'PaymentMethod', 'TransactionMonth', 'Quarter', 'IsWeekend',
    'SeasonalityLabel', 'ExpertiseCategoryMatch',
]


def _as_float(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number, got {value!r}.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number, got {value!r}.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite, got {value!r}.")
    return number


def _check_choice(value: str, choices: list[str], field: str) -> str:
    if value not in choices:
        raise ValueError(f"{field} must be one of {choices}, got {value!r}.")
    return value


def validate_course_inputs(
    course_category: str,
    course_level: str,
    course_price: float,
    course_duration: float,
    teacher_experience: float,
    teacher_rating: float,
    course_type: str = 'Paid',
    course_rating: float = 4.0,
    payment_method: str = 'Credit Card',
) -> dict:
    """Validate and normalize dashboard inputs.

    Returns a dict with normalized values. Free courses always have price 0.
    Raises ValueError with a user-facing message for invalid input.
    """
    category = _check_choice(course_category, COURSE_CATEGORIES, 'Course category')
    level = _check_choice(course_level, COURSE_LEVELS, 'Course level')
    ctype = _check_choice(course_type, COURSE_TYPES, 'Course type')
    payment = _check_choice(payment_method, PAYMENT_METHODS, 'Payment method')

    price = _as_float(course_price, 'Course price')
    duration = _as_float(course_duration, 'Course duration')
    rating = _as_float(course_rating, 'Course rating')
    experience = _as_float(teacher_experience, 'Teacher experience')
    t_rating = _as_float(teacher_rating, 'Teacher rating')

    if price < MIN_PRICE or price > MAX_PRICE:
        raise ValueError(f"Course price must be between ${MIN_PRICE:.0f} and ${MAX_PRICE:.0f}; got {price:.2f}.")
    if duration < MIN_DURATION or duration > MAX_DURATION:
        raise ValueError(f"Course duration must be between {MIN_DURATION:.0f} and {MAX_DURATION:.0f} hours; got {duration:.1f}.")
    if rating < MIN_RATING or rating > MAX_RATING:
        raise ValueError(f"Course rating must be between {MIN_RATING:.1f} and {MAX_RATING:.1f}; got {rating:.2f}.")
    if t_rating < MIN_RATING or t_rating > MAX_RATING:
        raise ValueError(f"Teacher rating must be between {MIN_RATING:.1f} and {MAX_RATING:.1f}; got {t_rating:.2f}.")
    if experience < MIN_EXPERIENCE or experience > MAX_EXPERIENCE:
        raise ValueError(f"Teacher experience must be between {MIN_EXPERIENCE} and {MAX_EXPERIENCE} years; got {experience:.1f}.")

    if ctype == 'Free':
        if price != 0:
            price = 0.0
    elif price == 0:
        raise ValueError("Paid courses require a course price greater than $0. Select Free for a zero-price course.")

    return {
        'course_category': category,
        'course_level': level,
        'course_price': price,
        'course_duration': duration,
        'teacher_experience': int(round(experience)),
        'teacher_rating': t_rating,
        'course_type': ctype,
        'course_rating': rating,
        'payment_method': payment,
    }


def price_band(price: float) -> str:
    """Return the canonical price band, raising for unsupported prices."""
    value = _as_float(price, 'Course price')
    if value < MIN_PRICE or value > MAX_PRICE:
        raise ValueError(f"Course price must be between ${MIN_PRICE:.0f} and ${MAX_PRICE:.0f}; got {value:.2f}.")
    if value == 0:
        return 'Free'
    if value <= 50:
        return 'Budget'
    if value <= 100:
        return 'Standard'
    if value <= 200:
        return 'Premium'
    return 'Elite'


def duration_bucket(duration: float) -> str:
    """Return the canonical duration bucket."""
    value = _as_float(duration, 'Course duration')
    if value < MIN_DURATION or value > MAX_DURATION:
        raise ValueError(f"Course duration must be between {MIN_DURATION:.0f} and {MAX_DURATION:.0f} hours; got {value:.1f}.")
    if value <= 10:
        return 'Short'
    if value <= 25:
        return 'Medium'
    if value <= 50:
        return 'Long'
    return 'Extended'


def rating_tier(rating: float) -> str:
    value = _as_float(rating, 'Course rating')
    if value < MIN_RATING or value > MAX_RATING:
        raise ValueError(f"Course rating must be between {MIN_RATING:.1f} and {MAX_RATING:.1f}; got {value:.2f}.")
    if value >= 4.5:
        return 'Elite'
    if value >= 4.0:
        return 'High'
    if value >= 3.0:
        return 'Medium'
    return 'Low'


def experience_bucket(experience: float) -> str:
    value = _as_float(experience, 'Teacher experience')
    if value < MIN_EXPERIENCE or value > MAX_EXPERIENCE:
        raise ValueError(f"Teacher experience must be between {MIN_EXPERIENCE} and {MAX_EXPERIENCE} years; got {value:.1f}.")
    if value <= 2:
        return 'Junior'
    if value <= 5:
        return 'Mid'
    if value <= 10:
        return 'Senior'
    return 'Expert'


def seasonality_label(quarter: int) -> str:
    """Legacy helper for dataset generation; not part of the model schema."""
    if isinstance(quarter, bool):
        raise ValueError(f"Quarter must be an integer between 1 and 4; got {quarter!r}.")
    try:
        value = int(quarter)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"Quarter must be an integer between 1 and 4; got {quarter!r}."
        ) from exc
    if value != quarter or value < 1 or value > 4:
        raise ValueError(f"Quarter must be an integer between 1 and 4; got {quarter!r}.")
    return {1: 'NewYearRush', 2: 'Spring', 3: 'Summer', 4: 'YearEnd'}[value]


def encode_course_level(course_level: str) -> int:
    """Ordinal-encode a validated course level; unknown levels fail fast."""
    return {'Beginner': 1, 'Intermediate': 2, 'Advanced': 3}[
        _check_choice(course_level, COURSE_LEVELS, 'Course level')
    ]


def teacher_rating_score(teacher_rating: float) -> float:
    """Fixed 1-5 normalization shared by training and inference."""
    value = _as_float(teacher_rating, 'Teacher rating')
    if value < MIN_RATING or value > MAX_RATING:
        raise ValueError(f"Teacher rating must be between {MIN_RATING:.1f} and {MAX_RATING:.1f}; got {value:.2f}.")
    return (value - MIN_RATING) / (MAX_RATING - MIN_RATING)


def build_feature_row(
    course_category: str,
    course_level: str,
    course_price: float,
    course_duration: float,
    teacher_experience: float,
    teacher_rating: float,
    course_type: str = 'Paid',
    course_rating: float = 4.0,
    payment_method: str = 'Credit Card',
) -> dict:
    """Build one canonical feature row. No transaction-only defaults leak in."""
    values = validate_course_inputs(
        course_category, course_level, course_price, course_duration,
        teacher_experience, teacher_rating, course_type, course_rating,
        payment_method,
    )
    return {
        'CoursePrice': values['course_price'],
        'CourseDuration': values['course_duration'],
        'CourseRating': values['course_rating'],
        'TeacherRating': values['teacher_rating'],
        'YearsOfExperience': values['teacher_experience'],
        'EncodedCourseLevel': encode_course_level(values['course_level']),
        'TeacherRatingScore': teacher_rating_score(values['teacher_rating']),
        'CourseCategory': values['course_category'],
        'CourseType': values['course_type'],
        'PriceBand': price_band(values['course_price']),
        'DurationBucket': duration_bucket(values['course_duration']),
        'RatingTier': rating_tier(values['course_rating']),
        'ExperienceBucket': experience_bucket(values['teacher_experience']),
    }


def build_feature_frame(**kwargs) -> pd.DataFrame:
    """Return a one-row DataFrame in the canonical model column order."""
    return pd.DataFrame([build_feature_row(**kwargs)], columns=FEATURE_COLUMNS)


def assert_feature_frame_contract(frame: pd.DataFrame) -> None:
    """Raise if a feature frame does not match the canonical schema/order."""
    missing = [c for c in FEATURE_COLUMNS if c not in frame.columns]
    extra = [c for c in frame.columns if c not in FEATURE_COLUMNS]
    if missing or extra:
        raise AssertionError(f"Feature contract mismatch: missing={missing}, extra={extra}.")
    if list(frame.columns) != FEATURE_COLUMNS:
        raise AssertionError(f"Feature order mismatch: {list(frame.columns)} != {FEATURE_COLUMNS}.")
