"""
utils.py — Shared utility functions for EduPro Streamlit dashboard.

Covers: data loading, model inference, KPI computation,
chart generation, and SHAP explanation helpers.

This module now uses the shared edup package for configuration,
feature engineering, business facts, and model operations.
"""

import math
import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np

try:
    import joblib
except ImportError:
    joblib = None

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Ensure the shared package is importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Backward-compatible constants for app.py and tests
DATA_PATH = os.path.join(BASE_DIR, '..', 'data', 'processed_data.csv')
MODELS_DIR = os.path.join(BASE_DIR, '..', 'models')

# Import from shared package
from edup.config import (
    COURSE_CATEGORIES,
    COURSE_LEVELS,
    COURSE_TYPES,
    PAYMENT_METHODS,
    MIN_PRICE,
    MAX_PRICE,
    MIN_DURATION,
    MAX_DURATION,
    MIN_RATING,
    MAX_RATING,
    MIN_EXPERIENCE,
    MAX_EXPERIENCE,
    FEATURE_COLUMNS,
    FORECAST_REQUIRED_COLUMNS,
)
from edup.data import load_processed_data
from edup.analytics import (
    compute_kpis,
    compute_business_facts,
    enrollment_reference,
    price_demand_diagnostics,
    revenue_scenarios,
)
from edup.features import (
    validate_course_inputs,
    build_feature_frame,
    build_feature_row,
)
from edup.models import load_enrollment_model, predict_enrollment, ModelLoadError
from edup.forecasting import load_forecast_results as _load_forecast_results, ForecastError, _NO_OVERRIDE
from edup.schema import validate_forecast_payload
from edup.exceptions import DataUnavailableError, DataContractError, ModelLoadError as EdupModelLoadError, ForecastError as EdupForecastError, DashboardError

# Expose joblib for backward compatibility with tests
try:
    import joblib
except ImportError:
    joblib = None


def load_forecast_results():
    """Wrapper that passes app's joblib and MODELS_DIR to the shared forecasting module."""
    # Read joblib and MODELS_DIR at call time to allow patching in tests
    import sys
    app_utils = sys.modules.get('app.utils')
    jl = getattr(app_utils, 'joblib', _NO_OVERRIDE) if app_utils else _NO_OVERRIDE
    models_dir = getattr(app_utils, 'MODELS_DIR', None) if app_utils else None
    return _load_forecast_results(_joblib_override=jl, models_dir=models_dir)

# Expose feature_contract for backward compatibility with tests
class _FeatureContract:
    FEATURE_COLUMNS = FEATURE_COLUMNS

feature_contract = _FeatureContract()

# ─── Chart Generators ─────────────────────────────────────────────────────────
# These are dashboard-specific and remain in app/utils.py

def chart_category_revenue(df: pd.DataFrame):
    cat_rev = df.groupby("CourseCategory")["Amount"].sum().reset_index()
    cat_rev.columns = ["Category", "Revenue"]
    cat_rev = cat_rev.sort_values("Revenue", ascending=True)
    fig = px.bar(
        cat_rev,
        x="Revenue",
        y="Category",
        orientation="h",
        title="Total Revenue by Course Category",
        color="Revenue",
        color_continuous_scale="Blues",
        labels={"Revenue": "Total Revenue ($)", "Category": "Category"},
    )
    fig.update_layout(coloraxis_showscale=False, height=420)
    return fig


def chart_monthly_revenue(df: pd.DataFrame):
    monthly = df.groupby([df["TransactionDate"].dt.to_period("M")])["Amount"].sum().reset_index()
    monthly["TransactionDate"] = monthly["TransactionDate"].astype(str)
    fig = px.line(
        monthly,
        x="TransactionDate",
        y="Amount",
        title="Monthly Revenue Trend",
        labels={"Amount": "Revenue ($)", "TransactionDate": "Month"},
        markers=True,
    )
    fig.update_traces(line_color="steelblue", line_width=2.5)
    fig.update_layout(height=360)
    return fig


def chart_top_courses(df: pd.DataFrame, n: int = 10):
    course_rev = df.groupby(["CourseID", "CourseName"])["Amount"].sum().reset_index()
    course_rev.columns = ["CourseID", "CourseName", "Revenue"]
    top = course_rev.nlargest(n, "Revenue")
    fig = px.bar(
        top,
        x="Revenue",
        y="CourseName",
        orientation="h",
        title=f"Top {n} Courses by Revenue",
        color="Revenue",
        color_continuous_scale="Blues",
        labels={"Revenue": "Total Revenue ($)", "CourseName": "Course"},
    )
    fig.update_layout(coloraxis_showscale=False, height=400)
    return fig


def chart_enrollment_by_category(df: pd.DataFrame):
    enroll = df.groupby("CourseCategory")["TransactionID"].count().reset_index()
    enroll.columns = ["Category", "Enrollments"]
    enroll = enroll.sort_values("Enrollments", ascending=False)
    fig = px.bar(
        enroll,
        x="Category",
        y="Enrollments",
        title="Enrollment Count by Category",
        color="Enrollments",
        color_continuous_scale="Blues",
        labels={"Enrollments": "Enrollments", "Category": "Category"},
    )
    fig.update_layout(xaxis_tickangle=-45, coloraxis_showscale=False, height=380)
    return fig


def chart_payment_methods(df: pd.DataFrame):
    paid = df[df["Amount"] > 0]
    pm = paid.groupby("PaymentMethod")["Amount"].agg(["sum", "count"]).reset_index()
    pm.columns = ["Method", "Revenue", "Count"]
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Revenue Share", "Transaction Count"),
        specs=[[{"type": "domain"}, {"type": "domain"}]],
    )

    fig.add_trace(
        go.Pie(
            labels=pm["Method"],
            values=pm["Revenue"],
            name="Revenue",
            hole=0.4,
            marker_colors=["#1f77b4", "#4c9be8", "#89c4f4"],
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Pie(
            labels=pm["Method"],
            values=pm["Count"],
            name="Count",
            hole=0.4,
            marker_colors=["#1f77b4", "#4c9be8", "#89c4f4"],
        ),
        row=1,
        col=2,
    )
    fig.update_layout(title="Payment Method Analysis", height=380, showlegend=True)
    return fig


def chart_teacher_performance(df: pd.DataFrame):
    teachers = df.groupby(["TeacherID", "TeacherName"]).agg(
        Revenue=("Amount", "sum"),
        Enrollments=("TransactionID", "count"),
        Rating=("TeacherRating", "first"),
    ).reset_index()

    fig = px.scatter(
        teachers,
        x="Rating",
        y="Revenue",
        size="Enrollments",
        hover_name="TeacherName",
        color="Revenue",
        color_continuous_scale="Blues",
        title="Teacher Rating vs Revenue (bubble = enrollments)",
        labels={"Rating": "Teacher Rating", "Revenue": "Revenue ($)"},
    )
    fig.update_layout(height=400)
    return fig


def chart_category_revenue_efficiency(df: pd.DataFrame):
    """Revenue per enrollment versus average price; not a profit calculation."""
    cat = df.groupby("CourseCategory").agg(
        Revenue=("Amount", "sum"),
        Enrollments=("TransactionID", "count"),
        AvgPrice=("CoursePrice", "mean"),
        AvgRating=("CourseRating", "mean"),
    ).reset_index()
    cat["RevenuePerEnrollment"] = cat["Revenue"] / cat["Enrollments"].replace(0, 1)

    fig = px.scatter(
        cat,
        x="AvgPrice",
        y="RevenuePerEnrollment",
        size="Enrollments",
        color="AvgRating",
        hover_name="CourseCategory",
        text="CourseCategory",
        color_continuous_scale="Blues",
        title="Category Revenue Efficiency (no cost or margin data)",
        labels={
            "AvgPrice": "Avg Course Price ($)",
            "RevenuePerEnrollment": "Revenue per Enrollment ($)",
            "AvgRating": "Avg Rating",
        },
    )
    fig.update_traces(textposition="top center", textfont_size=9)
    fig.update_layout(height=480)
    return fig


# ─── Prediction Contract and Transparent Revenue Arithmetic ──────────────────

def _build_input_row(
    course_category,
    course_level,
    course_price,
    course_duration,
    teacher_experience,
    teacher_rating,
    course_type="Paid",
    course_rating=4.0,
    payment_method="Credit Card",
):
    """Construct the shared canonical feature row (backward compatible).

    PaymentMethod is accepted for API compatibility but is intentionally not a
    course-level demand feature. TransactionMonth/Quarter/IsWeekend are not
    accepted because they are not known at course-design time.
    """
    return build_feature_frame(
        course_category=course_category,
        course_level=course_level,
        course_price=course_price,
        course_duration=course_duration,
        teacher_experience=teacher_experience,
        teacher_rating=teacher_rating,
        course_type=course_type,
        course_rating=course_rating,
        payment_method=payment_method,
    )


def calculate_expected_revenue(course_type: str, course_price: float, reference_enrollments: float) -> float:
    """Arithmetic expected revenue, not a model forecast.

    The dataset shows that paid courses are paid for every transaction and free
    courses have zero amount, so expected revenue is price x reference
    enrollments for Paid and $0 for Free. This is an accounting calculation.
    """
    if course_type not in COURSE_TYPES:
        raise ValueError(f"course_type must be one of {COURSE_TYPES}.")
    if isinstance(course_price, bool) or isinstance(reference_enrollments, bool):
        raise ValueError("Price and reference enrollments must be numeric.")
    try:
        price = float(course_price)
        enrollments = float(reference_enrollments)
    except (TypeError, ValueError) as exc:
        raise ValueError("Price and reference enrollments must be numeric.") from exc
    if not math.isfinite(price) or not math.isfinite(enrollments):
        raise ValueError("Price and reference enrollments must be finite.")
    if price < MIN_PRICE or price > MAX_PRICE:
        raise ValueError(
            f"Price must be between ${MIN_PRICE:.0f} and ${MAX_PRICE:.0f}."
        )
    if enrollments < 0:
        raise ValueError("Reference enrollments cannot be negative.")
    if course_type == "Free":
        return 0.0
    return price * enrollments


def estimate_enrollment_reference(df: pd.DataFrame | None = None) -> tuple[dict | None, str | None]:
    """Return the historical course-enrollment reference distribution."""
    if df is None:
        try:
            df = load_processed_data()
        except DataUnavailableError as exc:
            return None, f"Processed data not available: {exc}"
    try:
        ref = enrollment_reference(df)
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"Could not compute enrollment reference: {exc}"
    if ref["n_courses"] == 0:
        return None, "Processed data contains no courses."
    return ref, None


def get_business_facts(df: pd.DataFrame | None = None) -> dict:
    """Load and compute the data-verified business facts."""
    if df is None:
        df = load_processed_data()
    return compute_business_facts(df)


def get_price_demand_diagnostics(df: pd.DataFrame | None = None) -> dict:
    """Return evidence on whether price response is identifiable."""
    if df is None:
        df = load_processed_data()
    return price_demand_diagnostics(df)


def get_pricing_scenarios(
    base_price: float,
    reference_enrollments: float,
    assumed_change_pct: float = 0.0,
    prices: list[float] | None = None,
) -> pd.DataFrame:
    """Transparent scenario table; no optimum and no estimated elasticity."""
    return revenue_scenarios(
        base_price, reference_enrollments, assumed_change_pct, prices
    )


# ─── SHAP Explainability ─────────────────────────────────────────────────────

def compute_shap_values(model_pipe, X_sample, num_features, cat_features):
    """Compute SHAP values with an explainer appropriate to the estimator."""
    import shap

    preprocessor = model_pipe.named_steps["preprocessor"]
    final_model = model_pipe.named_steps["model"]

    X_transformed = preprocessor.transform(X_sample)
    try:
        ohe = preprocessor.named_transformers_["cat"]
        cat_names = list(ohe.get_feature_names_out(cat_features))
    except Exception:
        cat_names = []

    all_names = list(num_features) + cat_names
    X_df = pd.DataFrame(X_transformed, columns=all_names[: X_transformed.shape[1]])

    if hasattr(final_model, "feature_importances_"):
        explainer = shap.TreeExplainer(final_model)
    elif hasattr(final_model, "coef_"):
        explainer = shap.LinearExplainer(final_model, X_df)
    else:
        explainer = shap.Explainer(final_model, X_df)

    shap_values = explainer.shap_values(X_df)
    if isinstance(shap_values, list):
        shap_values = shap_values[0]
    return np.asarray(shap_values), X_df, explainer