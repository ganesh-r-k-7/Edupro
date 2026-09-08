"""
Notebook 04: Model Training
EduPro Predictive Modeling Project

Trains and tunes regression models for:
- Model 1: Enrollment Count prediction
- Model 2: Course Revenue prediction
- Model 3: Category-Level Revenue prediction
"""

import pandas as pd
import numpy as np
import os
import joblib
import warnings
warnings.filterwarnings('ignore')

from sklearn.model_selection import train_test_split, cross_val_score, RandomizedSearchCV
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
    print(f"Loaded: {df.shape}")
    return df


def build_preprocessor():
    """Construct sklearn ColumnTransformer for numeric + categorical features."""
    numeric_transformer = StandardScaler()
    categorical_transformer = OneHotEncoder(handle_unknown='ignore', sparse_output=False)

    preprocessor = ColumnTransformer(transformers=[
        ('num', numeric_transformer, NUMERIC_FEATURES),
        ('cat', categorical_transformer, CATEGORICAL_FEATURES),
    ])
    return preprocessor


def prepare_enrollment_target(df):
    """Aggregate enrollment count per course as prediction target."""
    enrollment = df.groupby('CourseID').agg(
        EnrollmentCount=('TransactionID', 'count'),
        CoursePrice=('CoursePrice', 'first'),
        CourseDuration=('CourseDuration', 'first'),
        CourseRating=('CourseRating', 'first'),
        TeacherRating=('TeacherRating', 'first'),
        YearsOfExperience=('YearsOfExperience', 'first'),
        EncodedCourseLevel=('EncodedCourseLevel', 'first'),
        TeacherRatingScore=('TeacherRatingScore', 'first'),
        ExpertiseCategoryMatch=('ExpertiseCategoryMatch', 'first'),
        TransactionMonth=('TransactionMonth', 'median'),
        Quarter=('Quarter', 'median'),
        IsWeekend=('IsWeekend', 'mean'),
        CourseCategory=('CourseCategory', 'first'),
        CourseType=('CourseType', 'first'),
        PriceBand=('PriceBand', 'first'),
        DurationBucket=('DurationBucket', 'first'),
        RatingTier=('RatingTier', 'first'),
        ExperienceBucket=('ExperienceBucket', 'first'),
        SeasonalityLabel=('SeasonalityLabel', 'first'),
        PaymentMethod=('PaymentMethod', 'first'),
    ).reset_index()
    return enrollment


def get_all_models():
    """Return dict of all candidate models."""
    return {
        'LinearRegression': LinearRegression(),
        'Ridge': Ridge(alpha=1.0, random_state=RANDOM_STATE),
        'Lasso': Lasso(alpha=0.1, random_state=RANDOM_STATE),
        'RandomForest': RandomForestRegressor(n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1),
        'GradientBoosting': GradientBoostingRegressor(n_estimators=200, random_state=RANDOM_STATE),
        'XGBoost': XGBRegressor(n_estimators=200, random_state=RANDOM_STATE,
                                 verbosity=0, eval_metric='rmse'),
    }


def evaluate_model(model, X_test, y_test):
    """Compute MAE, RMSE, and R2 on test set."""
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)
    return {'MAE': mae, 'RMSE': rmse, 'R2': r2}


def train_and_select_best(X_train, X_test, y_train, y_test, preprocessor, task_name):
    """Train all models, evaluate, and return best pipeline."""
    results = {}
    trained_pipelines = {}

    for name, model in get_all_models().items():
        pipe = Pipeline([('preprocessor', preprocessor), ('model', model)])
        pipe.fit(X_train, y_train)
        metrics = evaluate_model(pipe, X_test, y_test)
        results[name] = metrics
        trained_pipelines[name] = pipe
        print(f"  {name:22s} MAE={metrics['MAE']:.2f}  RMSE={metrics['RMSE']:.2f}  R2={metrics['R2']:.4f}")

    best_name = max(results, key=lambda k: results[k]['R2'])
    print(f"\n  Best model for {task_name}: {best_name} (R2={results[best_name]['R2']:.4f})")
    return trained_pipelines[best_name], best_name, results


def tune_xgboost(X_train, y_train, preprocessor):
    """Tune XGBoost hyperparameters with RandomizedSearchCV."""
    param_dist = {
        'model__n_estimators': [100, 200, 300],
        'model__max_depth': [3, 5, 7],
        'model__learning_rate': [0.05, 0.1, 0.2],
        'model__subsample': [0.7, 0.8, 1.0],
        'model__colsample_bytree': [0.7, 0.8, 1.0],
    }
    pipe = Pipeline([
        ('preprocessor', preprocessor),
        ('model', XGBRegressor(random_state=RANDOM_STATE, verbosity=0))
    ])
    search = RandomizedSearchCV(pipe, param_dist, n_iter=20, cv=3,
                                 scoring='r2', random_state=RANDOM_STATE, n_jobs=-1)
    search.fit(X_train, y_train)
    print(f"  Best XGBoost params: {search.best_params_}")
    print(f"  Best CV R2: {search.best_score_:.4f}")
    return search.best_estimator_


def train_enrollment_model(df):
    """Train enrollment prediction model (Model 1)."""
    print("\n=== MODEL 1: Enrollment Count Prediction ===")
    enrollment_df = prepare_enrollment_target(df)
    all_feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    available = [c for c in all_feats if c in enrollment_df.columns]
    X = enrollment_df[available]
    y = enrollment_df['EnrollmentCount']

    num_available = [c for c in NUMERIC_FEATURES if c in X.columns]
    cat_available = [c for c in CATEGORICAL_FEATURES if c in X.columns]

    preprocessor = ColumnTransformer(transformers=[
        ('num', StandardScaler(), num_available),
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cat_available),
    ])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE)

    best_pipe, best_name, results = train_and_select_best(
        X_train, X_test, y_train, y_test, preprocessor, 'Enrollment')

    tuned_pipe = tune_xgboost(X_train, y_train, preprocessor)
    tuned_metrics = evaluate_model(tuned_pipe, X_test, y_test)
    print(f"  Tuned XGBoost => MAE={tuned_metrics['MAE']:.2f}  RMSE={tuned_metrics['RMSE']:.2f}  R2={tuned_metrics['R2']:.4f}")

    final_pipe = tuned_pipe if tuned_metrics['R2'] > results[best_name]['R2'] else best_pipe
    joblib.dump(final_pipe, os.path.join(MODELS_DIR, 'enrollment_model.pkl'))
    print(f"  Enrollment model saved.")
    return final_pipe


def train_revenue_model(df):
    """Train course revenue prediction model (Model 2)."""
    print("\n=== MODEL 2: Course Revenue Prediction ===")
    all_feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    available = [c for c in all_feats if c in df.columns]
    X = df[available]
    y = df['Amount']

    num_available = [c for c in NUMERIC_FEATURES if c in X.columns]
    cat_available = [c for c in CATEGORICAL_FEATURES if c in X.columns]

    preprocessor = ColumnTransformer(transformers=[
        ('num', StandardScaler(), num_available),
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cat_available),
    ])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE)

    best_pipe, best_name, results = train_and_select_best(
        X_train, X_test, y_train, y_test, preprocessor, 'Revenue')

    tuned_pipe = tune_xgboost(X_train, y_train, preprocessor)
    tuned_metrics = evaluate_model(tuned_pipe, X_test, y_test)
    print(f"  Tuned XGBoost => MAE={tuned_metrics['MAE']:.2f}  RMSE={tuned_metrics['RMSE']:.2f}  R2={tuned_metrics['R2']:.4f}")

    final_pipe = tuned_pipe if tuned_metrics['R2'] > results[best_name]['R2'] else best_pipe
    joblib.dump(final_pipe, os.path.join(MODELS_DIR, 'revenue_model.pkl'))

    preprocessor_only = preprocessor
    preprocessor_only.fit(X_train)
    joblib.dump(preprocessor_only, os.path.join(MODELS_DIR, 'preprocessing_pipeline.pkl'))
    print(f"  Revenue model and preprocessing pipeline saved.")
    return final_pipe


def run_model_training():
    df = load_data()
    enroll_model = train_enrollment_model(df)
    revenue_model = train_revenue_model(df)
    print("\nAll models trained and saved to models/")
    return enroll_model, revenue_model


if __name__ == '__main__':
    run_model_training()
