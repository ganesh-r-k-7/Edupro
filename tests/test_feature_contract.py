import pandas as pd
import pytest

from edup.config import (
    FEATURE_COLUMNS,
    EXCLUDED_TRANSACTION_FEATURES,
)
from edup.features.features import (
    price_band,
    duration_bucket,
    rating_tier,
    experience_bucket,
    build_feature_row,
    validate_course_inputs,
    encode_course_level,
    build_feature_frame,
    assert_feature_frame_contract,
)


@pytest.mark.parametrize('price,expected', [
    (0, 'Free'), (0.01, 'Budget'), (50, 'Budget'), (50.01, 'Standard'),
    (100, 'Standard'), (100.01, 'Premium'), (200, 'Premium'),
    (200.01, 'Elite'), (500, 'Elite'),
])
def test_price_band_boundaries(price, expected):
    assert price_band(price) == expected


@pytest.mark.parametrize('price', [-0.01, 500.01, float('nan')])
def test_price_band_rejects_unsupported_values(price):
    with pytest.raises(ValueError):
        price_band(price)


@pytest.mark.parametrize('duration,expected', [
    (1, 'Short'), (10, 'Short'), (10.1, 'Medium'), (25, 'Medium'),
    (25.1, 'Long'), (50, 'Long'), (50.1, 'Extended'), (200, 'Extended'),
])
def test_duration_bucket_boundaries(duration, expected):
    assert duration_bucket(duration) == expected


@pytest.mark.parametrize('duration', [0, 200.01, float('nan')])
def test_duration_bucket_rejects_unsupported_values(duration):
    with pytest.raises(ValueError):
        duration_bucket(duration)


def test_rating_and_experience_buckets():
    assert rating_tier(4.5) == 'Elite'
    assert rating_tier(4.0) == 'High'
    assert rating_tier(3.0) == 'Medium'
    assert rating_tier(2.9) == 'Low'
    assert experience_bucket(0) == 'Junior'
    assert experience_bucket(3) == 'Mid'
    assert experience_bucket(7) == 'Senior'
    assert experience_bucket(11) == 'Expert'


def test_build_feature_row_has_exact_contract():
    row = build_feature_row(
        'Business', 'Beginner', 99, 20, 5, 4.0, 'Paid', 4.0, 'PayPal')
    assert list(row) == FEATURE_COLUMNS
    assert row['CourseType'] == 'Paid'
    assert row['CourseRating'] == 4.0
    assert row.get('PaymentMethod', True)
    for excluded in EXCLUDED_TRANSACTION_FEATURES:
        assert excluded not in row


def test_free_course_normalizes_price_and_keeps_inputs():
    values = validate_course_inputs(
        'Business', 'Beginner', 99, 20, 5, 4.0, 'Free', 3.5, 'PayPal')
    assert values['course_price'] == 0
    assert values['course_type'] == 'Free'
    assert values['course_rating'] == 3.5
    row = build_feature_row(
        'Business', 'Beginner', 99, 20, 5, 4.0, 'Free', 3.5, 'PayPal')
    assert row['CoursePrice'] == 0
    assert row['PriceBand'] == 'Free'
    assert row['RatingTier'] == 'Medium'


def test_paid_course_requires_positive_price():
    with pytest.raises(ValueError, match='Paid courses require'):
        validate_course_inputs(
            'Business', 'Beginner', 0, 20, 5, 4.0, 'Paid', 4.0, 'Credit Card')


def test_invalid_category_level_and_payment_raise():
    with pytest.raises(ValueError, match='Course category'):
        build_feature_row('Nope', 'Beginner', 99, 20, 5, 4.0)
    with pytest.raises(ValueError, match='Course level'):
        build_feature_row('Business', 'Nope', 99, 20, 5, 4.0)
    with pytest.raises(ValueError, match='Payment method'):
        build_feature_row('Business', 'Beginner', 99, 20, 5, 4.0,
                          payment_method='Cash')


def test_feature_frame_contract_and_order():
    frame = build_feature_frame(
        course_category='Business', course_level='Intermediate',
        course_price=99, course_duration=20, teacher_experience=5,
        teacher_rating=4.0)
    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == FEATURE_COLUMNS
    assert_feature_frame_contract(frame)