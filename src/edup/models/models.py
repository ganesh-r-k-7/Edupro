"""
models.py — Model training, evaluation, and prediction for EduPro.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Lasso, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from edup.config import (
    MODELS_DIR,
    NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    EXCLUDED_TRANSACTION_FEATURES,
    RANDOM_STATE,
    CV_FOLDS,
    TEST_SIZE,
)
from edup.features import validate_course_inputs, build_feature_frame, assert_feature_frame_contract
from edup.analytics import amount_price_identity_summary
from edup.data import load_processed_data
from edup.exceptions import DataUnavailableError, ModelLoadError


def _json_metrics(metrics: dict[str, float]) -> dict[str, float]:
    return {k: float(v) for k, v in metrics.items()}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)


def get_all_models() -> dict[str, Any]:
    """Return dict of all candidate models."""
    return {
        "LinearRegression": LinearRegression(),
        "Ridge": Ridge(alpha=1.0, random_state=RANDOM_STATE),
        "Lasso": Lasso(alpha=0.1, random_state=RANDOM_STATE),
        "RandomForest": RandomForestRegressor(n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1),
        "GradientBoosting": GradientBoostingRegressor(n_estimators=200, random_state=RANDOM_STATE),
        "XGBoost": XGBRegressor(n_estimators=200, random_state=RANDOM_STATE, verbosity=0, eval_metric="rmse"),
    }


def evaluate_model(model: Any, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, float]:
    """Compute MAE, RMSE, and R2 on test set."""
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)
    return {"MAE": mae, "RMSE": rmse, "R2": r2}


def audit_revenue_target(
    df: pd.DataFrame | None = None,
    models_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Document why transaction Amount is not a valid regression target.

    Amount is an accounting identity with CoursePrice, so any model using
    CoursePrice to predict Amount is reconstructing the target rather than
    forecasting revenue. The legacy revenue_model.pkl is deliberately left
    untouched and is not used by the dashboard.
    """
    if df is None:
        df = load_processed_data()
    if models_dir is None:
        models_dir = MODELS_DIR
    models_dir = Path(models_dir)

    print("\n=== REVENUE TARGET AUDIT (NO MODEL TRAINED) ===")
    identity = amount_price_identity_summary(df)
    status = "retired_identity" if identity["identity_holds"] else "needs_review"
    payload = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": status,
        "target": "Amount (transaction amount)",
        "reason": (
            "Amount equals CoursePrice for every paid transaction and is 0 for "
            "every free transaction. CoursePrice is also a feature, so the target "
            "is an accounting identity, not a forecastable revenue outcome."
        ),
        "recommended_target": (
            "No defensible revenue target is available in Phase 1. Use the "
            "transparent price x reference-enrollment calculator instead."
        ),
        "evidence": identity,
        "legacy_artifact": str(models_dir / "revenue_model.pkl"),
    }
    _write_json(models_dir / "revenue_target_audit.json", payload)
    print(f"  Amount-price identity holds: {identity['identity_holds']}")
    print(f"  Paid/free is course-level: {identity['paid_free_is_course_level']}")
    print("  Revenue regressor retired; legacy artifact preserved but not used.")
    return payload


def prepare_enrollment_target(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to 60 course rows using stable course-level features.

    Teacher attributes are averaged within a course. Transaction-only fields
    (payment method, month, quarter, weekend) are deliberately excluded.
    """
    enrollment = df.groupby("CourseID").agg(
        EnrollmentCount=("TransactionID", "count"),
        CoursePrice=("CoursePrice", "first"),
        CourseDuration=("CourseDuration", "first"),
        CourseRating=("CourseRating", "first"),
        TeacherRating=("TeacherRating", "mean"),
        YearsOfExperience=("YearsOfExperience", "mean"),
        EncodedCourseLevel=("EncodedCourseLevel", "first"),
        CourseCategory=("CourseCategory", "first"),
        CourseType=("CourseType", "first"),
    ).reset_index()

    enrollment["YearsOfExperience"] = enrollment["YearsOfExperience"].round().astype(int)
    from edup.features import teacher_rating_score, price_band, duration_bucket, rating_tier, experience_bucket
    enrollment["TeacherRatingScore"] = enrollment["TeacherRating"].apply(teacher_rating_score)
    enrollment["PriceBand"] = enrollment["CoursePrice"].apply(price_band)
    enrollment["DurationBucket"] = enrollment["CourseDuration"].apply(duration_bucket)
    enrollment["RatingTier"] = enrollment["CourseRating"].apply(rating_tier)
    enrollment["ExperienceBucket"] = enrollment["YearsOfExperience"].apply(experience_bucket)
    return enrollment


def train_enrollment_model(
    df: pd.DataFrame | None = None,
    cross_val_score_func=None,
    models_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Train and evaluate enrollment candidates against a mean baseline.

    Selection uses 5-fold CV on the training split only. The test split is
    touched once. If the selected model does not beat the baseline on both CV
    and the final test, no Phase 1 model artifact is saved.
    """
    # Allow cross_val_score to be overridden for testing
    cv_score = cross_val_score_func or cross_val_score
    if models_dir is None:
        models_dir = MODELS_DIR
    models_dir = Path(models_dir)

    if df is None:
        df = load_processed_data()

    print("\n=== MODEL 1: Enrollment Count Prediction ===")
    enrollment_df = prepare_enrollment_target(df)
    missing = [c for c in FEATURE_COLUMNS if c not in enrollment_df.columns]
    if missing:
        raise ValueError(f"Enrollment feature contract is missing columns: {missing}")

    X = enrollment_df[FEATURE_COLUMNS].copy()
    y = enrollment_df["EnrollmentCount"].astype(float)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )

    preprocessor = ColumnTransformer(transformers=[
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
    ])
    cv = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    baseline_cv = -cv_score(
        DummyRegressor(strategy="mean"), X_train, y_train, cv=cv,
        scoring="neg_root_mean_squared_error"
    ).mean()
    baseline = DummyRegressor(strategy="mean").fit(X_train, y_train)
    baseline_test = evaluate_model(baseline, X_test, y_test)

    cv_results = {}
    pipelines = {}
    for name, model in get_all_models().items():
        pipe = Pipeline([("preprocessor", preprocessor), ("model", model)])
        scores = cv_score(
            pipe, X_train, y_train, cv=cv,
            scoring="neg_root_mean_squared_error"
        )
        cv_results[name] = float(-scores.mean())
        pipelines[name] = pipe
        print(f"  {name:22s} CV RMSE={cv_results[name]:.3f}")

    best_name = min(cv_results, key=cv_results.get)
    best_pipe = pipelines[best_name]
    best_pipe.fit(X_train, y_train)
    best_test = evaluate_model(best_pipe, X_test, y_test)

    use_model = bool(
        cv_results[best_name] < baseline_cv
        and best_test["RMSE"] < baseline_test["RMSE"]
    )
    metrics = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "target": "EnrollmentCount (course-level)",
        "n_courses": int(len(enrollment_df)),
        "features": FEATURE_COLUMNS,
        "excluded_transaction_features": EXCLUDED_TRANSACTION_FEATURES,
        "split": {"test_size": TEST_SIZE, "random_state": RANDOM_STATE},
        "cv_folds": CV_FOLDS,
        "baseline": {
            "name": "DummyRegressor(mean)",
            "cv_rmse": float(baseline_cv),
            "test": _json_metrics(baseline_test),
        },
        "selected_model": best_name,
        "candidate_cv_rmse": {k: float(v) for k, v in cv_results.items()},
        "selected_test": _json_metrics(best_test),
        "use_model": use_model,
        "decision": (
            "use model" if use_model
            else "do not use model: it does not beat the mean baseline on both CV and test"
        ),
    }

    if use_model:
        model_path = models_dir / "enrollment_model_phase1.pkl"
        joblib.dump(best_pipe, model_path)
        metrics["model_path"] = str(model_path)
        print(f"  Selected {best_name}; saved Phase 1 model to {model_path}")
    else:
        metrics["model_path"] = None
        print(f"  Selected {best_name}, but it does not beat the mean baseline.")
        print("  No Phase 1 enrollment model artifact was saved.")

    _write_json(models_dir / "enrollment_metrics.json", metrics)
    print(f"  Baseline test RMSE={baseline_test['RMSE']:.3f}, "
          f"selected test RMSE={best_test['RMSE']:.3f}")
    return metrics


def load_enrollment_model(model_path: Path | str | None = None) -> Pipeline:
    """Load the enrollment model pipeline."""
    model_path = model_path or (MODELS_DIR / "enrollment_model_phase1.pkl")
    if not os.path.exists(model_path):
        # Fall back to legacy model
        legacy_path = MODELS_DIR / "enrollment_model.pkl"
        if os.path.exists(legacy_path):
            model_path = legacy_path
        else:
            raise ModelLoadError(f"Enrollment model not found at {model_path} or {legacy_path}")
    try:
        return joblib.load(model_path)
    except Exception as exc:
        raise ModelLoadError(f"Failed to load enrollment model: {exc}") from exc


def predict_enrollment(
    model: Pipeline,
    course_category: str,
    course_level: str,
    course_price: float,
    course_duration: float,
    teacher_experience: float,
    teacher_rating: float,
    course_type: str = "Paid",
    course_rating: float = 4.0,
    payment_method: str = "Credit Card",
) -> float:
    """Predict enrollment for a course configuration."""
    # Validate inputs through shared contract
    values = validate_course_inputs(
        course_category, course_level, course_price, course_duration,
        teacher_experience, teacher_rating, course_type, course_rating,
        payment_method,
    )

    # Build feature frame using shared feature engineering
    X = build_feature_frame(**values)
    assert_feature_frame_contract(X)

    # Predict
    pred = model.predict(X)[0]
    return float(max(0, pred))