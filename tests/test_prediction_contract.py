import pandas as pd
import pytest

pytest.importorskip('plotly')
from app import utils


def test_build_input_row_uses_form_inputs():
    base = utils._build_input_row(
        'Business', 'Beginner', 99, 20, 5, 4.0, 'Paid', 4.0, 'Credit Card')
    free = utils._build_input_row(
        'Business', 'Beginner', 0, 20, 5, 4.0, 'Free', 3.0, 'PayPal')
    assert list(base.columns) == utils.feature_contract.FEATURE_COLUMNS
    assert base.loc[0, 'CourseType'] == 'Paid'
    assert free.loc[0, 'CourseType'] == 'Free'
    assert free.loc[0, 'PriceBand'] == 'Free'
    assert free.loc[0, 'RatingTier'] == 'Medium'
    assert 'PaymentMethod' not in base.columns


def test_payment_method_is_informational_only():
    a = utils._build_input_row(
        'Business', 'Beginner', 99, 20, 5, 4.0, 'Paid', 4.0, 'Credit Card')
    b = utils._build_input_row(
        'Business', 'Beginner', 99, 20, 5, 4.0, 'Paid', 4.0, 'PayPal')
    pd.testing.assert_frame_equal(a, b)


@pytest.mark.parametrize('price,course_type', [
    (0, 'Free'), (50, 'Paid'), (100, 'Paid'), (200, 'Paid'),
    (400, 'Paid'), (500, 'Paid'),
])
def test_supported_price_boundaries_do_not_crash(price, course_type):
    row = utils._build_input_row(
        'Business', 'Beginner', price, 20, 5, 4.0, course_type, 4.0, 'Credit Card')
    assert row.loc[0, 'CoursePrice'] == price


def test_price_above_supported_range_has_clear_error():
    with pytest.raises(ValueError, match='between'):
        utils._build_input_row(
            'Business', 'Beginner', 500.01, 20, 5, 4.0, 'Paid', 4.0, 'Credit Card')


def test_expected_revenue_is_arithmetic_and_free_is_zero():
    assert utils.calculate_expected_revenue('Paid', 100, 10) == 1000
    assert utils.calculate_expected_revenue('Free', 100, 10) == 0
    with pytest.raises(ValueError):
        utils.calculate_expected_revenue('Paid', -1, 10)
    with pytest.raises(ValueError):
        utils.calculate_expected_revenue('Paid', 100, -1)


def test_missing_data_returns_error_not_exception():
    ref, err = utils.estimate_enrollment_reference(pd.DataFrame())
    assert ref is None
    assert err


def test_legacy_revenue_model_is_not_loaded_by_inference():
    source = open(utils.__file__, encoding='utf-8').read()
    assert 'predict_revenue' not in source
    assert "revenue_model.pkl" not in source
