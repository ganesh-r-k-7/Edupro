import importlib.util
import os

import pytest

pytest.importorskip('sklearn')
pytest.importorskip('xgboost')

import feature_contract as fc


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_training_module():
    path = os.path.join(ROOT, 'notebooks', '04_model_training.py')
    spec = importlib.util.spec_from_file_location('edup_training_phase2_hardening', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_feature_equal(expected, actual, column):
    if isinstance(expected, str):
        assert actual == expected, column
    else:
        assert actual == pytest.approx(expected), column


def test_course_target_aggregation_matches_explicit_groupby(df):
    target = _load_training_module().prepare_enrollment_target(df).set_index('CourseID')

    for course_id, group in df.groupby('CourseID'):
        row = target.loc[course_id]
        assert int(row['EnrollmentCount']) == len(group)
        assert row['TeacherRating'] == pytest.approx(group['TeacherRating'].mean())
        assert int(row['YearsOfExperience']) == int(round(group['YearsOfExperience'].mean()))
        assert row['CoursePrice'] == pytest.approx(group['CoursePrice'].iloc[0])
        assert row['CourseDuration'] == pytest.approx(group['CourseDuration'].iloc[0])
        assert row['CourseRating'] == pytest.approx(group['CourseRating'].iloc[0])
        assert row['CourseCategory'] == group['CourseCategory'].iloc[0]
        assert row['CourseType'] == group['CourseType'].iloc[0]
        assert int(row['EncodedCourseLevel']) == int(group['EncodedCourseLevel'].iloc[0])


def test_course_target_counts_cover_all_transactions(df):
    target = _load_training_module().prepare_enrollment_target(df)
    assert int(target['EnrollmentCount'].sum()) == len(df)
    assert target['CourseID'].is_unique


def test_target_rows_match_inference_built_from_raw_course_data(df):
    target = _load_training_module().prepare_enrollment_target(df)

    for _, target_row in target.iterrows():
        group = df[df['CourseID'] == target_row['CourseID']]
        expected = fc.build_feature_row(
            course_category=group['CourseCategory'].iloc[0],
            course_level=group['CourseLevel'].iloc[0],
            course_price=group['CoursePrice'].iloc[0],
            course_duration=group['CourseDuration'].iloc[0],
            teacher_experience=int(round(group['YearsOfExperience'].mean())),
            teacher_rating=group['TeacherRating'].mean(),
            course_type=group['CourseType'].iloc[0],
            course_rating=group['CourseRating'].iloc[0],
        )
        for column in fc.FEATURE_COLUMNS:
            _assert_feature_equal(expected[column], target_row[column], column)


def test_course_level_inputs_are_constant_within_each_course(df):
    for column in ['CoursePrice', 'CourseDuration', 'CourseRating',
                   'CourseCategory', 'CourseType', 'CourseLevel',
                   'EncodedCourseLevel']:
        assert (df.groupby('CourseID')[column].nunique() == 1).all(), column


def test_feature_lists_are_disjoint_complete_and_ordered():
    assert not set(fc.NUMERIC_FEATURES) & set(fc.CATEGORICAL_FEATURES)
    assert fc.FEATURE_COLUMNS == fc.NUMERIC_FEATURES + fc.CATEGORICAL_FEATURES
    assert not set(fc.EXCLUDED_TRANSACTION_FEATURES) & set(fc.FEATURE_COLUMNS)


def test_training_target_levels_are_within_inference_domain(df):
    target = _load_training_module().prepare_enrollment_target(df)
    assert set(target['EncodedCourseLevel']).issubset({1, 2, 3})
