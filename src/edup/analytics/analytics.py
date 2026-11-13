"""
analytics.py — Business analytics and KPI computation for EduPro.
"""

from __future__ import annotations

import pandas as pd

from edup.analytics.business_facts import (
    amount_price_identity_summary,
    break_even_enrollment_change,
    compute_business_facts,
    enrollment_reference,
    price_demand_diagnostics,
    revenue_scenarios,
)


def compute_kpis(df: pd.DataFrame) -> dict[str, float | int | str]:
    """Compute key performance indicators for the executive dashboard."""
    if df is None or len(df) == 0:
        raise ValueError("KPI computation requires at least one transaction.")

    total_revenue = df["Amount"].sum()
    total_enrollments = len(df)
    avg_course_rating = df["CourseRating"].mean()
    unique_courses = df["CourseID"].nunique()
    unique_teachers = df["TeacherID"].nunique()
    paid_ratio = (df["Amount"] > 0).mean() * 100
    top_category = df.groupby("CourseCategory")["Amount"].sum().idxmax()
    avg_revenue_per_course = total_revenue / unique_courses if unique_courses > 0 else 0

    return {
        "total_revenue": float(total_revenue),
        "total_enrollments": int(total_enrollments),
        "avg_course_rating": float(avg_course_rating),
        "unique_courses": int(unique_courses),
        "unique_teachers": int(unique_teachers),
        "paid_ratio": float(paid_ratio),
        "top_category": top_category,
        "avg_revenue_per_course": float(avg_revenue_per_course),
    }


# Re-export business_facts functions
__all__ = [
    "compute_kpis",
    "compute_business_facts",
    "amount_price_identity_summary",
    "enrollment_reference",
    "price_demand_diagnostics",
    "revenue_scenarios",
    "break_even_enrollment_change",
]
