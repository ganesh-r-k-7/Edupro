"""
config.py — Centralized configuration for EduPro.

Single source of truth for paths, feature lists, categorical domains,
binning edges, and numeric bounds used across training, inference,
and the dashboard.
"""

from __future__ import annotations

from pathlib import Path

# ─── Project Root ──────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
MODELS_DIR = ROOT_DIR / "models"
REPORTS_DIR = ROOT_DIR / "reports"

# ─── Raw / Processed Data Paths ────────────────────────────────────────────────

RAW_DATA_PATH = DATA_DIR / "EduPro_Online_Platform.xlsx"
PROCESSED_DATA_PATH = DATA_DIR / "processed_data.csv"

# ─── Categorical Domains ───────────────────────────────────────────────────────

COURSE_CATEGORIES = [
    "Programming",
    "Design",
    "Business",
    "Marketing",
    "Data Science",
    "Machine Learning",
    "Cybersecurity",
    "Project Management",
    "Finance",
    "Artificial Intelligence",
    "Web Development",
    "Digital Marketing",
]

COURSE_LEVELS = ["Beginner", "Intermediate", "Advanced"]
COURSE_TYPES = ["Paid", "Free"]
PAYMENT_METHODS = ["Credit Card", "PayPal", "Bank Transfer"]

# ─── Binning Labels and Edges ──────────────────────────────────────────────────

PRICE_BANDS = ["Free", "Budget", "Standard", "Premium", "Elite"]
DURATION_BUCKETS = ["Short", "Medium", "Long", "Extended"]
RATING_TIERS = ["Low", "Medium", "High", "Elite"]
EXPERIENCE_BUCKETS = ["Junior", "Mid", "Senior", "Expert"]
SEASONALITY_LABELS = ["NewYearRush", "Spring", "Summer", "YearEnd"]

PRICE_BAND_EDGES = [0.0, 50.0, 100.0, 200.0, 500.0]
DURATION_BUCKET_EDGES = [0.0, 10.0, 25.0, 50.0, 200.0]

# ─── Numeric Bounds ────────────────────────────────────────────────────────────

MAX_PRICE = 500.0
MIN_PRICE = 0.0
MAX_DURATION = 200.0
MIN_DURATION = 1.0
MIN_RATING = 1.0
MAX_RATING = 5.0
MIN_EXPERIENCE = 0
MAX_EXPERIENCE = 30

# ─── Feature Column Definitions ────────────────────────────────────────────────

NUMERIC_FEATURES = [
    "CoursePrice",
    "CourseDuration",
    "CourseRating",
    "TeacherRating",
    "YearsOfExperience",
    "EncodedCourseLevel",
    "TeacherRatingScore",
]

CATEGORICAL_FEATURES = [
    "CourseCategory",
    "CourseType",
    "PriceBand",
    "DurationBucket",
    "RatingTier",
    "ExperienceBucket",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Explicitly excluded from the course-level schema because they are
# transaction-level, unknown at course-design time, or arbitrarily
# aggregated in the legacy course-level dataset.
EXCLUDED_TRANSACTION_FEATURES = [
    "PaymentMethod",
    "TransactionMonth",
    "Quarter",
    "IsWeekend",
    "SeasonalityLabel",
    "ExpertiseCategoryMatch",
]

# All engineered columns (for dropping before re-running feature engineering)
ENGINEERED_COLUMNS = [
    "PriceBand",
    "DurationBucket",
    "RatingTier",
    "EncodedCourseLevel",
    "ExperienceBucket",
    "TeacherRatingScore",
    "ExpertiseCategoryMatch",
    "TransactionMonth",
    "Quarter",
    "Year",
    "DayOfWeek",
    "WeekOfYear",
    "IsWeekend",
    "SeasonalityLabel",
    "EnrollmentCount",
    "TotalRevenue",
    "AverageRevenue",
    "RevenuePerEnrollment",
    "MonthlyRevenue",
    "RollingRevenueAverage",
    "RevenueGrowthRate",
    "MonthlyRevenueTrend",
]

# ─── Forecast Payload Schema ───────────────────────────────────────────────────

FORECAST_REQUIRED_COLUMNS = ["ds", "yhat", "yhat_lower", "yhat_upper"]

# ─── Model Training Configuration ──────────────────────────────────────────────

RANDOM_STATE = 42
CV_FOLDS = 5
TEST_SIZE = 0.2

# ─── Dashboard Configuration ───────────────────────────────────────────────────

PAGE_OPTIONS = [
    "Executive Dashboard",
    "Course Demand Prediction",
    "Revenue Forecasting",
    "Feature Importance Explorer",
    "Category Analytics",
]

# ─── Version / Metadata ────────────────────────────────────────────────────────

PROJECT_VERSION = "1.3.0"
PHASE = "Phase 3"
