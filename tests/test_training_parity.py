import importlib.util
import json
import os

import pandas as pd
import pytest

pytest.importorskip('sklearn')
pytest.importorskip('xgboost')

import feature_contract as fc


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_training_module():
    path = os.path.join(ROOT, 'notebooks', '04_model_training.py')
    spec = importlib.util.spec_from_file_location('edup_training_phase2', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_training_rows_match_inference_feature_contract(df):
    module = _load_training_module()
    target = module.prepare_enrollment_target(df)
    level_map = {1: 'Beginner', 2: 'Intermediate', 3: 'Advanced'}

    for _, row in target.iterrows():
        expected = fc.build_feature_row(
            course_category=row['CourseCategory'],
            course_level=level_map[int(row['EncodedCourseLevel'])],
            course_price=row['CoursePrice'],
            course_duration=row['CourseDuration'],
            teacher_experience=row['YearsOfExperience'],
            teacher_rating=row['TeacherRating'],
            course_type=row['CourseType'],
            course_rating=row['CourseRating'],
        )
        for column in fc.FEATURE_COLUMNS:
            if isinstance(expected[column], str):
                assert expected[column] == row[column], column
            else:
                assert expected[column] == pytest.approx(row[column]), column


def test_course_level_preparation_is_shuffle_invariant(df):
    module = _load_training_module()
    first = module.prepare_enrollment_target(df)
    shuffled = module.prepare_enrollment_target(
        df.sample(frac=1, random_state=7).reset_index(drop=True)
    )
    pd.testing.assert_frame_equal(
        first.sort_values('CourseID').reset_index(drop=True),
        shuffled.sort_values('CourseID').reset_index(drop=True),
        check_exact=False,
        rtol=1e-12,
    )


def test_training_selection_uses_training_split_only(monkeypatch, tmp_path, df):
    module = _load_training_module()
    monkeypatch.setattr(module, 'MODELS_DIR', str(tmp_path))
    seen_sizes = []
    real_cross_val_score = module.cross_val_score

    def spy(estimator, X, y, **kwargs):
        seen_sizes.append(len(X))
        return real_cross_val_score(estimator, X, y, **kwargs)

    monkeypatch.setattr(module, 'cross_val_score', spy)
    metrics = module.train_enrollment_model(df)

    assert seen_sizes
    assert set(seen_sizes) == {48}
    assert metrics['n_courses'] == 60
    assert metrics['use_model'] is False
    assert metrics['selected_model'] in metrics['candidate_cv_rmse']
    assert (tmp_path / 'enrollment_metrics.json').exists()
    persisted = json.loads((tmp_path / 'enrollment_metrics.json').read_text())
    assert persisted['selected_model'] == metrics['selected_model']


def test_revenue_audit_writes_only_to_temp_directory(monkeypatch, tmp_path, df):
    module = _load_training_module()
    monkeypatch.setattr(module, 'MODELS_DIR', str(tmp_path))
    payload = module.audit_revenue_target(df)
    assert payload['status'] == 'retired_identity'
    assert payload['evidence']['identity_holds'] is True
    path = tmp_path / 'revenue_target_audit.json'
    assert path.exists()
    assert json.loads(path.read_text())['status'] == 'retired_identity'
