"""
Notebook 05: Model Evaluation
EduPro Predictive Modeling Project

Generates evaluation metrics, prediction vs actual plots,
residual plots, feature importance plots, and model comparison tables.
"""

import pandas as pd
import numpy as np
import os
import joblib
import warnings
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
warnings.filterwarnings('ignore')

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

RANDOM_STATE = 42
DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed_data.csv')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
REPORTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')

NUMERIC_FEATURES = [
    'CoursePrice', 'CourseDuration', 'CourseRating',
    'TeacherRating', 'YearsOfExperience', 'EncodedCourseLevel',
    'TeacherRatingScore', 'ExpertiseCategoryMatch',
    'TransactionMonth', 'Quarter', 'IsWeekend'
]
CATEGORICAL_FEATURES = [
    'CourseCategory', 'CourseType', 'PriceBand',
    'DurationBucket', 'RatingTier', 'ExperienceBucket',
    'SeasonalityLabel', 'PaymentMethod'
]


def load_data():
    df = pd.read_csv(DATA_PATH, parse_dates=['TransactionDate'])
    return df


def plot_prediction_vs_actual(y_test, y_pred, title, filename):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].scatter(y_test, y_pred, alpha=0.4, color='steelblue', edgecolors='none', s=20)
    lim_min = min(y_test.min(), y_pred.min())
    lim_max = max(y_test.max(), y_pred.max())
    axes[0].plot([lim_min, lim_max], [lim_min, lim_max], 'r--', lw=2, label='Perfect Prediction')
    axes[0].set_xlabel('Actual', fontsize=11)
    axes[0].set_ylabel('Predicted', fontsize=11)
    axes[0].set_title(f'{title}: Actual vs Predicted', fontsize=12, fontweight='bold')
    axes[0].legend()

    residuals = y_test - y_pred
    axes[1].scatter(y_pred, residuals, alpha=0.4, color='steelblue', edgecolors='none', s=20)
    axes[1].axhline(0, color='red', linestyle='--', lw=2)
    axes[1].set_xlabel('Predicted', fontsize=11)
    axes[1].set_ylabel('Residuals', fontsize=11)
    axes[1].set_title(f'{title}: Residual Plot', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, filename), dpi=150, bbox_inches='tight')
    plt.close()


def plot_feature_importance(model_pipe, feature_names_num, feature_names_cat, title, filename):
    """Extract and plot feature importances from the XGBoost/RF step."""
    final_model = model_pipe.named_steps['model']
    preprocessor = model_pipe.named_steps['preprocessor']

    try:
        ohe = preprocessor.named_transformers_['cat']
        cat_names = list(ohe.get_feature_names_out(feature_names_cat))
    except Exception:
        cat_names = []

    all_names = list(feature_names_num) + cat_names

    if hasattr(final_model, 'feature_importances_'):
        importances = final_model.feature_importances_
        n = min(len(importances), len(all_names))
        feat_imp = pd.Series(importances[:n], index=all_names[:n]).sort_values(ascending=False)
        top20 = feat_imp.head(20)

        fig, ax = plt.subplots(figsize=(10, 7))
        sns.barplot(x=top20.values, y=top20.index, palette='Blues_r', ax=ax)
        ax.set_title(f'{title}: Top 20 Feature Importances', fontsize=12, fontweight='bold')
        ax.set_xlabel('Importance Score', fontsize=11)
        plt.tight_layout()
        plt.savefig(os.path.join(REPORTS_DIR, filename), dpi=150, bbox_inches='tight')
        plt.close()
        return feat_imp
    else:
        print(f"  Model does not support feature importances.")
        return None


def compare_models(results_dict, title, filename):
    """Create bar chart comparing model metrics."""
    df = pd.DataFrame(results_dict).T
    df = df.sort_values('R2', ascending=False)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    metrics = ['MAE', 'RMSE', 'R2']
    colors = ['#e74c3c', '#e67e22', '#2ecc71']

    for ax, metric, color in zip(axes, metrics, colors):
        df[metric].plot(kind='bar', ax=ax, color=color, alpha=0.85, edgecolor='black')
        ax.set_title(f'{metric}', fontsize=12, fontweight='bold')
        ax.set_xlabel('Model', fontsize=10)
        ax.set_ylabel(metric, fontsize=10)
        ax.tick_params(axis='x', rotation=30)
        for bar in ax.patches:
            ax.annotate(f'{bar.get_height():.3f}',
                        (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        ha='center', va='bottom', fontsize=8)

    plt.suptitle(f'Model Comparison: {title}', fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, filename), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nModel comparison table:\n{df.round(4).to_string()}")
    return df


def evaluate_revenue_model():
    """Full evaluation of revenue prediction model."""
    print("\n=== Evaluating Revenue Model ===")
    df = load_data()

    num_available = [c for c in NUMERIC_FEATURES if c in df.columns]
    cat_available = [c for c in CATEGORICAL_FEATURES if c in df.columns]

    X = df[num_available + cat_available]
    y = df['Amount']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)

    model = joblib.load(os.path.join(MODELS_DIR, 'revenue_model.pkl'))
    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    print(f"Revenue Model => MAE={mae:.2f}, RMSE={rmse:.2f}, R2={r2:.4f}")

    plot_prediction_vs_actual(y_test.values, y_pred, 'Revenue Prediction', 'revenue_pred_vs_actual.png')
    feat_imp = plot_feature_importance(model, num_available, cat_available,
                                        'Revenue Model', 'revenue_feature_importance.png')

    # Benchmark all models for comparison
    results = {}
    preprocessor = ColumnTransformer(transformers=[
        ('num', StandardScaler(), num_available),
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cat_available),
    ])
    models = {
        'LinearRegression': LinearRegression(),
        'Ridge': Ridge(alpha=1.0),
        'Lasso': Lasso(alpha=0.1),
        'RandomForest': RandomForestRegressor(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1),
        'GradientBoosting': GradientBoostingRegressor(n_estimators=100, random_state=RANDOM_STATE),
        'XGBoost': XGBRegressor(n_estimators=100, random_state=RANDOM_STATE, verbosity=0),
    }
    for name, m in models.items():
        pipe = Pipeline([('preprocessor', preprocessor), ('model', m)])
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_test)
        results[name] = {
            'MAE': mean_absolute_error(y_test, preds),
            'RMSE': np.sqrt(mean_squared_error(y_test, preds)),
            'R2': r2_score(y_test, preds),
        }

    compare_models(results, 'Revenue Prediction', 'revenue_model_comparison.png')
    return feat_imp


def run_evaluation():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    feat_imp = evaluate_revenue_model()
    print("\nModel evaluation complete. Plots saved to reports/")
    return feat_imp


if __name__ == '__main__':
    run_evaluation()
