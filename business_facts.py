"""
business_facts.py — Data-verified business facts and transparent pricing scenarios.

This module does not forecast demand and does not estimate price elasticity.
It reports what the checked-in dataset supports and exposes arithmetic
scenario calculations with explicit assumptions.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from feature_contract import MAX_PRICE, MIN_PRICE


def _require_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def compute_business_facts(df: pd.DataFrame) -> dict:
    """Compute the headline facts from the processed transaction dataset."""
    _require_columns(df, ['Amount', 'CoursePrice', 'CourseID', 'CourseCategory',
                          'CourseType', 'TransactionID', 'TransactionDate'])

    amount = pd.to_numeric(df['Amount'], errors='coerce').fillna(0.0)
    paid_mask = amount > 0
    free_mask = ~paid_mask
    total_rows = int(len(df))
    total_revenue = float(amount.sum())

    category_revenue = (
        df.assign(_Amount=amount)
        .groupby('CourseCategory')['_Amount']
        .sum()
        .sort_values(ascending=False)
    )
    top3 = category_revenue.head(3)
    top3_share = float(top3.sum() / total_revenue * 100) if total_revenue else 0.0

    dates = pd.to_datetime(df['TransactionDate'], errors='coerce')
    quarters = dates.dt.quarter
    quarterly = {}
    for q in [1, 2, 3, 4]:
        mask = quarters == q
        quarterly[f'Q{q}'] = {
            'transactions': int(mask.sum()),
            'revenue': float(amount[mask].sum()),
            'paid_transactions': int((paid_mask & mask).sum()),
        }

    paid_courses = int(df.loc[paid_mask, 'CourseID'].nunique())
    free_courses = int(df.loc[free_mask, 'CourseID'].nunique())

    return {
        'transactions': total_rows,
        'paid_transactions': int(paid_mask.sum()),
        'free_transactions': int(free_mask.sum()),
        'paid_share_pct': float(paid_mask.mean() * 100),
        'free_share_pct': float(free_mask.mean() * 100),
        'total_revenue': total_revenue,
        'unique_courses': int(df['CourseID'].nunique()),
        'paid_courses': paid_courses,
        'free_courses': free_courses,
        'category_revenue': {k: float(v) for k, v in category_revenue.items()},
        'top3_categories': list(top3.index),
        'top3_revenue': {k: float(v) for k, v in top3.items()},
        'top3_share_pct': top3_share,
        'machine_learning_revenue': float(category_revenue.get('Machine Learning', 0.0)),
        'marketing_revenue': float(category_revenue.get('Marketing', 0.0)),
        'quarterly': quarterly,
        'date_min': str(dates.min().date()) if dates.notna().any() else None,
        'date_max': str(dates.max().date()) if dates.notna().any() else None,
    }


def amount_price_identity_summary(df: pd.DataFrame) -> dict:
    """Test whether Amount is an accounting identity with CoursePrice."""
    _require_columns(df, ['Amount', 'CoursePrice', 'CourseID', 'CourseType'])
    amount = pd.to_numeric(df['Amount'], errors='coerce').fillna(0.0)
    price = pd.to_numeric(df['CoursePrice'], errors='coerce').fillna(0.0)
    paid = amount > 0
    free = ~paid

    paid_mismatch = int((paid & ~np.isclose(amount, price, atol=1e-9)).sum())
    free_mismatch = int((free & ~np.isclose(amount, 0.0, atol=1e-9)).sum())
    mixed_courses = 0
    if len(df):
        per_course = df.assign(_paid=paid).groupby('CourseID')['_paid'].nunique()
        mixed_courses = int((per_course > 1).sum())

    denom = float(np.std(amount) * np.std(price))
    correlation = float(np.corrcoef(amount, price)[0, 1]) if len(df) > 1 and denom > 0 else None
    return {
        'paid_rows': int(paid.sum()),
        'free_rows': int(free.sum()),
        'paid_mismatches': paid_mismatch,
        'free_mismatches': free_mismatch,
        'mixed_courses': mixed_courses,
        'amount_price_correlation': correlation,
        'identity_holds': paid_mismatch == 0 and free_mismatch == 0,
        'paid_free_is_course_level': mixed_courses == 0,
    }


def enrollment_reference(df: pd.DataFrame) -> dict:
    """Return the historical course-enrollment reference distribution."""
    _require_columns(df, ['CourseID', 'TransactionID'])
    counts = df.groupby('CourseID')['TransactionID'].count().astype(float)
    if counts.empty:
        return {
            'n_courses': 0, 'mean': 0.0, 'median': 0.0, 'std': 0.0,
            'p10': 0.0, 'p90': 0.0, 'min': 0.0, 'max': 0.0,
        }
    return {
        'n_courses': int(len(counts)),
        'mean': float(counts.mean()),
        'median': float(counts.median()),
        'std': float(counts.std(ddof=1)) if len(counts) > 1 else 0.0,
        'p10': float(np.percentile(counts, 10)),
        'p90': float(np.percentile(counts, 90)),
        'min': float(counts.min()),
        'max': float(counts.max()),
    }


def price_demand_diagnostics(df: pd.DataFrame) -> dict:
    """Report whether the dataset can identify a price-demand response."""
    _require_columns(df, ['CourseID', 'CoursePrice', 'CourseType', 'Amount', 'TransactionID'])
    amount = pd.to_numeric(df['Amount'], errors='coerce').fillna(0.0)
    price = pd.to_numeric(df['CoursePrice'], errors='coerce').fillna(0.0)
    work = df.assign(_amount=amount, _price=price)
    courses = (
        work.groupby('CourseID')
        .agg(
            enrollments=('TransactionID', 'count'),
            revenue=('_amount', 'sum'),
            price=('_price', 'first'),
            course_type=('CourseType', 'first'),
            unique_prices=('_price', 'nunique'),
        )
        .reset_index()
    )
    paid = courses[courses['course_type'] == 'Paid']

    def corr(a: pd.Series, b: pd.Series) -> float | None:
        if len(a) < 2 or float(a.std()) == 0 or float(b.std()) == 0:
            return None
        return float(np.corrcoef(a, b)[0, 1])

    return {
        'n_courses': int(len(courses)),
        'n_paid_courses': int(len(paid)),
        'unique_paid_prices': int(paid['price'].nunique()),
        'courses_with_multiple_prices': int((courses['unique_prices'] > 1).sum()),
        'paid_price_enrollment_corr': corr(paid['price'], paid['enrollments']),
        'all_price_enrollment_corr': corr(courses['price'], courses['enrollments']),
        'paid_price_revenue_corr': corr(paid['price'], paid['revenue']),
        'enrollment_min': float(courses['enrollments'].min()) if len(courses) else 0.0,
        'enrollment_max': float(courses['enrollments'].max()) if len(courses) else 0.0,
        'elasticity_identifiable': False,
        'reason': (
            'Each course has a single observed price and there are no within-course '
            'price changes; paid-price/enrollment correlation is near zero. '
            'A causal price response cannot be estimated from this dataset.'
        ),
    }


def _finite_float(value, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric.") from exc
    if not np.isfinite(number):
        raise ValueError(f"{field} must be finite.")
    return number


def break_even_enrollment_change(old_price: float, new_price: float) -> float:
    """Return the enrollment change needed to keep revenue constant.

    A price increase requires a negative enrollment change. Returns NaN when
    either price is zero or invalid for the calculation.
    """
    old = _finite_float(old_price, 'old_price')
    new = _finite_float(new_price, 'new_price')
    if old <= 0 or new <= 0:
        return float('nan')
    return (old / new - 1.0) * 100.0


def revenue_scenarios(
    base_price: float,
    reference_enrollments: float,
    assumed_change_pct: float = 0.0,
    prices: Iterable[float] | None = None,
) -> pd.DataFrame:
    """Arithmetic scenario table with an explicit assumed enrollment change.

    This is not a demand model. The same assumed enrollment change is applied
    at every tested price; nothing is labelled or inferred as optimal.
    """
    base_price = _finite_float(base_price, 'base_price')
    reference_enrollments = _finite_float(reference_enrollments, 'reference_enrollments')
    assumed_change_pct = _finite_float(assumed_change_pct, 'assumed_change_pct')
    if base_price < MIN_PRICE or base_price > MAX_PRICE:
        raise ValueError(f"base_price must be between {MIN_PRICE:.0f} and {MAX_PRICE:.0f}.")
    if reference_enrollments < 0:
        raise ValueError("reference_enrollments cannot be negative.")
    if assumed_change_pct < -100 or assumed_change_pct > 100:
        raise ValueError("assumed_change_pct must be between -100 and 100.")

    default_prices = [0.0, 50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0]
    tested = [_finite_float(p, 'Scenario price') for p in (prices if prices is not None else default_prices)]
    if not tested:
        raise ValueError("At least one scenario price is required.")
    for p in tested:
        if p < MIN_PRICE or p > MAX_PRICE:
            raise ValueError(f"Scenario price must be between {MIN_PRICE:.0f} and {MAX_PRICE:.0f}; got {p:.2f}.")

    projected_enrollments = reference_enrollments * (1.0 + assumed_change_pct / 100.0)
    rows = []
    for p in tested:
        rows.append({
            'Price': p,
            'PriceChangePct': ((p / base_price - 1.0) * 100.0) if base_price > 0 else float('nan'),
            'AssumedEnrollmentChangePct': assumed_change_pct,
            'ProjectedEnrollments': projected_enrollments,
            'ProjectedRevenue': p * projected_enrollments,
            'BreakEvenEnrollmentChangePct': break_even_enrollment_change(base_price, p),
        })
    return pd.DataFrame(rows)
