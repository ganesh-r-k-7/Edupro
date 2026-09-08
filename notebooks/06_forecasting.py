"""
Notebook 06: Revenue Forecasting
EduPro Predictive Modeling Project

Builds time-series forecasting models using Prophet for:
- Monthly platform-wide revenue
- Category-level revenue trends
- Enrollment growth projections
"""

import pandas as pd
import numpy as np
import os
import warnings
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
warnings.filterwarnings('ignore')

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed_data.csv')
REPORTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')


def load_data():
    return pd.read_csv(DATA_PATH, parse_dates=['TransactionDate'])


def prepare_monthly_revenue(df):
    """Aggregate to monthly total revenue for Prophet."""
    monthly = df.groupby(pd.Grouper(key='TransactionDate', freq='MS'))['Amount'].sum().reset_index()
    monthly.columns = ['ds', 'y']
    monthly = monthly[monthly['y'] > 0].reset_index(drop=True)
    return monthly


def prepare_category_revenue(df, category):
    """Monthly revenue for a single course category."""
    sub = df[df['CourseCategory'] == category]
    monthly = sub.groupby(pd.Grouper(key='TransactionDate', freq='MS'))['Amount'].sum().reset_index()
    monthly.columns = ['ds', 'y']
    monthly = monthly[monthly['y'] >= 0].reset_index(drop=True)
    return monthly


def prepare_monthly_enrollments(df):
    """Monthly enrollment count."""
    monthly = df.groupby(pd.Grouper(key='TransactionDate', freq='MS'))['TransactionID'].count().reset_index()
    monthly.columns = ['ds', 'y']
    return monthly


def forecast_with_prophet(series_df, periods=6, freq='MS', title='Revenue Forecast', filename='forecast.png'):
    """Train Prophet model and generate future forecasts."""
    from prophet import Prophet

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode='multiplicative',
        changepoint_prior_scale=0.05,
    )
    model.fit(series_df)

    future = model.make_future_dataframe(periods=periods, freq=freq)
    forecast = model.predict(future)

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(series_df['ds'], series_df['y'], color='steelblue', lw=2, label='Actual', marker='o', ms=4)
    ax.plot(forecast['ds'], forecast['yhat'], color='darkorange', lw=2, label='Forecast', linestyle='--')
    ax.fill_between(forecast['ds'], forecast['yhat_lower'], forecast['yhat_upper'],
                    alpha=0.2, color='darkorange', label='Confidence Interval')
    ax.axvline(x=series_df['ds'].max(), color='gray', linestyle=':', lw=1.5, label='Forecast Start')
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.set_xlabel('Date')
    ax.set_ylabel('Value')
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, filename), dpi=150, bbox_inches='tight')
    plt.close()

    future_only = forecast[forecast['ds'] > series_df['ds'].max()]
    print(f"\n{title} - Next {periods} periods forecast:")
    print(future_only[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].to_string(index=False))
    return model, forecast


def forecast_with_arima_fallback(series_df, periods=6, title='Forecast', filename='arima_forecast.png'):
    """ARIMA-based fallback when Prophet is unavailable or as comparison."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    series = series_df.set_index('ds')['y']
    series.index = pd.DatetimeIndex(series.index, freq='MS')

    model = SARIMAX(series, order=(1, 1, 1), seasonal_order=(1, 0, 1, 12))
    result = model.fit(disp=False)

    forecast_res = result.get_forecast(steps=periods)
    forecast_mean = forecast_res.predicted_mean
    conf_int = forecast_res.conf_int()

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(series, color='steelblue', lw=2, label='Actual', marker='o', ms=4)
    ax.plot(forecast_mean, color='darkorange', lw=2, linestyle='--', label='ARIMA Forecast')
    ax.fill_between(conf_int.index, conf_int.iloc[:, 0], conf_int.iloc[:, 1],
                    alpha=0.2, color='darkorange')
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.set_xlabel('Date')
    ax.set_ylabel('Value')
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, filename), dpi=150, bbox_inches='tight')
    plt.close()
    return result, forecast_mean


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
    os.makedirs(REPORTS_DIR, exist_ok=True)
    df = load_data()
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

        import joblib
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
