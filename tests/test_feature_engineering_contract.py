import importlib.util
import os

import pandas as pd

from edup.config import (
    COURSE_CATEGORIES,
    COURSE_LEVELS,
    COURSE_TYPES,
    PAYMENT_METHODS,
    PRICE_BANDS,
    DURATION_BUCKETS,
    RATING_TIERS,
    EXPERIENCE_BUCKETS,
    SEASONALITY_LABELS,
    MAX_PRICE,
    MIN_PRICE,
    MAX_DURATION,
    MIN_DURATION,
    MIN_RATING,
    MAX_RATING,
    MIN_EXPERIENCE,
    MAX_EXPERIENCE,
    PRICE_BAND_EDGES,
    DURATION_BUCKET_EDGES,
    NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    EXCLUDED_TRANSACTION_FEATURES,
)
from edup.features.features import (
    price_band,
    duration_bucket,
    rating_tier,
    encode_course_level,
    experience_bucket,
    teacher_rating_score,
    seasonality_label,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_feature_module():
    path = os.path.join(ROOT, 'notebooks', '03_feature_engineering.py')
    spec = importlib.util.spec_from_file_location('edup_feature_engineering', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_feature_engineering_uses_canonical_contract(df):
    module = _load_feature_module()
    work = df.copy()
    work = module.add_price_band(work)
    work = module.add_duration_bucket(work)
    work = module.add_rating_tier(work)
    work = module.encode_course_level(work)
    work = module.add_experience_bucket(work)
    work = module.add_teacher_rating_score(work)
    work = module.add_expertise_category_match(work)
    work = module.add_time_features(work)

    assert work['PriceBand'].tolist() == df['CoursePrice'].apply(price_band).tolist()
    assert work['DurationBucket'].tolist() == df['CourseDuration'].apply(duration_bucket).tolist()
    assert work['RatingTier'].tolist() == df['CourseRating'].apply(rating_tier).tolist()
    assert work['EncodedCourseLevel'].tolist() == df['CourseLevel'].apply(encode_course_level).tolist()
    assert work['ExperienceBucket'].tolist() == df['YearsOfExperience'].apply(experience_bucket).tolist()
    expected_score = df['TeacherRating'].apply(teacher_rating_score)
    assert work['TeacherRatingScore'].tolist() == expected_score.tolist()
    assert work['SeasonalityLabel'].tolist() == df['TransactionDate'].dt.quarter.apply(seasonality_label).tolist()


def test_feature_engineering_is_idempotent_on_temporary_copy(tmp_path, df, monkeypatch):
    module = _load_feature_module()
    source = tmp_path / 'processed.csv'
    output = tmp_path / 'features.csv'
    df.to_csv(source, index=False)
    monkeypatch.setattr(module, 'DATA_PATH', str(source))
    monkeypatch.setattr(module, 'OUTPUT_PATH', str(output))

    first = module.run_feature_engineering()
    first_bytes = output.read_bytes()
    second = module.run_feature_engineering()
    second_bytes = output.read_bytes()

    assert first.shape == second.shape
    assert list(first.columns) == list(second.columns)
    assert first_bytes == second_bytes
    assert not any('_x' in c or '_y' in c for c in first.columns)
    assert len(pd.read_csv(output)) == len(df)