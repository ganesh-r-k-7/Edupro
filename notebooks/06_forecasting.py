"""
Notebook 06: Revenue Forecasting
EduPro Predictive Modeling Project

Builds time-series forecasting models using Prophet for:
- Monthly platform-wide revenue
- Category-level revenue trends
- Enrollment growth projections
"""

import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Ensure shared package is importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from edup.config import REPORTS_DIR, MODELS_DIR
from edup.data import load_processed_data
from edup.forecasting import (
    prepare_monthly_revenue,
    prepare_monthly_enrollments,
    prepare_category_revenue,
    forecast_with_prophet,
    forecast_with_arima_fallback,
)


def plot_category_growth_comparison(df):
    """Compare revenue growth trends across top categories."""
    monthly_cat = df.groupby(['CourseCategory', pd.Grouper(key='TransactionDate', freq='MS')])['Amount'].sum().reset_index()
    top_cats = df.groupby('CourseCategory')['Amount'].sum().nlargest(6).index.tolist()

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    axes = axes.flatten()

    for i, cat in enumerate(top_cats):
        sub = monthly_cat[monthly_cat['CourseCategory'] == cat]
        axes[i].plot(sub['TransactionDate'], sub['Amount'], color='steelblue', lw=2, marker='o', ms=4)
        axes[i].fill_between(sub['TransactionDate'], sub['Amount'], alpha=0.15, color='steelblue')
        axes[i].set_title(cat, fontsize=11, fontweight='bold')
        axes[i].set_xlabel('')
        axes[i].set_ylabel('Revenue ($)')
        axes[i].tick_params(axis='x', rotation=30)

    plt.suptitle('Monthly Revenue Trends by Top Course Categories', fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'eda_category_trends.png'), dpi=150, bbox_inches='tight')
    plt.close()


def run_forecasting():
    import pandas as pd
    import joblib

    os.makedirs(REPORTS_DIR, exist_ok=True)
    df = load_processed_data()
    print(f"Running forecasting on {df.shape[0]} records...")

    monthly_rev = prepare_monthly_revenue(df)
    plot_category_growth_comparison(df)

    try:
        revenue_model, revenue_forecast = forecast_with_prophet(
            monthly_rev, periods=6, title='Platform Monthly Revenue Forecast',
            filename='forecast_monthly_revenue.png')

        monthly_enroll = prepare_monthly_enrollments(df)
        enroll_model, enroll_forecast = forecast_with_prophet(
            monthly_enroll, periods=6, title='Monthly Enrollment Growth Forecast',
            filename='forecast_enrollments.png')

        top_category = df.groupby('CourseCategory')['Amount'].sum().idxmax()
        cat_rev = prepare_category_revenue(df, top_category)
        if len(cat_rev) >= 3:
            _, _ = forecast_with_prophet(
                cat_rev, periods=6,
                title=f'Revenue Forecast: {top_category}',
                filename='forecast_top_category.png')

        joblib.dump({'revenue': revenue_forecast, 'enrollment': enroll_forecast},
                    os.path.join(MODELS_DIR, 'forecast_results.pkl'))
        print("\nForecasting complete. Results saved.")
        return revenue_forecast, enroll_forecast

    except Exception as e:
        print(f"Prophet unavailable ({e}). Falling back to ARIMA...")
        _, _ = forecast_with_arima_fallback(
            monthly_rev, periods=6,
            title='Platform Monthly Revenue Forecast (ARIMA)',
            filename='forecast_monthly_revenue.png')
        print("ARIMA forecasting complete.")
        return None, None


if __name__ == '__main__':
    run_forecasting()