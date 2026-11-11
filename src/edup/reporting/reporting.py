"""
reporting.py — Report generation for EduPro.

Generates executive summary and research paper from data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from edup.config import REPORTS_DIR, MODELS_DIR
from edup.analytics import compute_business_facts, amount_price_identity_summary, enrollment_reference
from edup.data import load_processed_data


def generate_executive_summary(df: pd.DataFrame | None = None) -> str:
    """Generate executive summary markdown from data."""
    if df is None:
        df = load_processed_data()

    facts = compute_business_facts(df)
    identity = amount_price_identity_summary(df)
    enrollment = enrollment_reference(df)

    lines = [
        "# Executive Summary — EduPro Analytics Platform\n",
        f"**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M UTC')}\n",
        "## Platform Overview\n",
        f"- **Total Transactions:** {facts['transactions']:,}",
        f"- **Total Revenue:** ${facts['total_revenue']:,.2f}",
        f"- **Unique Courses:** {facts['unique_courses']}",
        f"- **Paid Courses:** {facts['paid_courses']} | **Free Courses:** {facts['free_courses']}",
        f"- **Paid Transaction Share:** {facts['paid_share_pct']:.2f}%",
        f"- **Free Transaction Share:** {facts['free_share_pct']:.2f}%\n",
        "## Revenue by Category\n",
    ]

    for cat, rev in facts["category_revenue"].items():
        lines.append(f"- **{cat}:** ${rev:,.2f}")

    lines.extend([
        "\n## Top 3 Revenue Categories",
        f"{', '.join(facts['top3_categories'])} — {facts['top3_share_pct']:.2f}% of total revenue\n",
        "## Key Data Facts\n",
        f"- Machine Learning Revenue: ${facts['machine_learning_revenue']:,.2f}",
        f"- Marketing Revenue: ${facts['marketing_revenue']:,.2f}",
        f"- Amount/Price Identity: {'Holds' if identity['identity_holds'] else 'Violated'}",
        f"- Paid/Free is Course-Level: {'Yes' if identity['paid_free_is_course_level'] else 'No'}\n",
        "## Enrollment Reference\n",
        f"- **Mean Enrollments per Course:** {enrollment['mean']:.1f}",
        f"- **Range (10th–90th percentile):** {enrollment['p10']:.0f}–{enrollment['p90']:.0f}",
        f"- **Courses Analyzed:** {enrollment['n_courses']}\n",
        "## Model Status\n",
        "- Revenue Model: Retired (target leakage — accounting identity)",
        "- Enrollment Model: Baseline comparison only (no model beats mean baseline)\n",
        "## Forecast\n",
        "- Prophet forecast cached but not backtested; treat as illustrative only.\n",
        "---\n",
        "*This summary is generated from data. Run `python run_pipeline.py` to regenerate.*",
    ])

    return "\n".join(lines)


def generate_research_paper(df: pd.DataFrame | None = None) -> str:
    """Generate research paper markdown from data."""
    if df is None:
        df = load_processed_data()

    facts = compute_business_facts(df)
    identity = amount_price_identity_summary(df)
    enrollment = enrollment_reference(df)

    lines = [
        "# EduPro Predictive Analytics — Research Paper\n",
        f"**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M UTC')}\n",
        "## Abstract\n",
        "This paper documents the EduPro predictive analytics platform, "
        "including data processing, feature engineering, model training, "
        "and dashboard deployment. The platform analyzes a synthetic dataset "
        "of 10,000 transactions across 60 courses, 60 teachers, and 3,000 users.\n",
        "## 1. Data Description\n",
        f"- **Transactions:** {facts['transactions']:,}",
        f"- **Date Range:** {facts['date_min']} to {facts['date_max']}",
        f"- **Users:** {df['UserID'].nunique():,}",
        f"- **Courses:** {facts['unique_courses']}",
        f"- **Teachers:** {df['TeacherID'].nunique():,}",
        f"- **Categories:** {len(facts['category_revenue'])}\n",
        "## 2. Target Definitions\n",
        "### 2.1 Revenue Target (Retired)\n",
        f"The transaction-level `Amount` target was found to be an accounting identity with "
        f"`CoursePrice` (correlation = {identity['amount_price_correlation']:.3f}). "
        f"Amount equals CoursePrice for all {identity['paid_rows']} paid rows and $0 for all "
        f"{identity['free_rows']} free rows. The legacy revenue model is preserved as "
        f"`models/revenue_model.pkl` but is not used for inference.\n",
        "### 2.2 Enrollment Target\n",
        f"Course-level `EnrollmentCount` aggregated from {enrollment['n_courses']} courses. "
        f"Distribution: mean={enrollment['mean']:.1f}, std={enrollment['std']:.1f}, "
        f"range=[{enrollment['min']:.0f}, {enrollment['max']:.0f}]. "
        f"Coefficient of variation: {enrollment['std']/enrollment['mean']*100:.1f}%.\n",
        "## 3. Feature Engineering\n",
        f"**Numeric Features ({len(df.columns)}):** CoursePrice, CourseDuration, CourseRating, "
        f"TeacherRating, YearsOfExperience, EncodedCourseLevel, TeacherRatingScore\n",
        f"**Categorical Features:** CourseCategory, CourseType, PriceBand, DurationBucket, "
        f"RatingTier, ExperienceBucket\n",
        f"**Excluded Transaction Features:** PaymentMethod, TransactionMonth, Quarter, "
        f"IsWeekend, SeasonalityLabel, ExpertiseCategoryMatch\n",
        "## 4. Model Training & Evaluation\n",
        "- **Split:** 80/20 random (random_state=42)",
        "- **CV:** 5-fold KFold (shuffle=True, random_state=42)",
        "- **Baseline:** DummyRegressor(strategy='mean')",
        "- **Candidates:** LinearRegression, Ridge, Lasso, RandomForest, GradientBoosting, XGBoost",
        "- **Selection Criterion:** Must beat baseline on both CV RMSE and test RMSE\n",
        "## 5. Results\n",
        f"- **Baseline CV RMSE:** (see enrollment_metrics.json)",
        f"- **Baseline Test RMSE:** (see enrollment_metrics.json)",
        "- **Selected Model:** (see enrollment_metrics.json)",
        "- **Model Beats Baseline:** (see enrollment_metrics.json — currently False)\n",
        "## 6. Price Elasticity\n",
        f"- Paid courses: {df[df['CourseType']=='Paid']['CourseID'].nunique()}",
        f"- Unique paid prices: {df[df['CourseType']=='Paid']['CoursePrice'].nunique()}",
        "- Courses with multiple prices: 0",
        "- Paid price/enrollment correlation: ~0.0\n",
        "A causal price response cannot be estimated from this dataset.\n",
        "## 7. Forecasting\n",
        "- Prophet model with yearly seasonality on 12 monthly points",
        "- No backtesting, no baseline comparison",
        "- Results cached in `models/forecast_results.pkl`\n",
        "## 8. Limitations\n",
        "1. Revenue target is an identity, not a forecastable outcome.",
        "2. Enrollment signal is near-uniform; no model beats the mean baseline.",
        "3. Price elasticity is not identifiable (no within-course price variation).",
        "4. Forecast is unbacktested and should not be used for planning.",
        "5. Data is synthetic; results may not generalize to real platforms.\n",
        "---\n",
        "*This paper is generated from data. Run `python run_pipeline.py` to regenerate.*",
    ]

    return "\n".join(lines)