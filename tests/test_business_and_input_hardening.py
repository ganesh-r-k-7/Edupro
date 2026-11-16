import math

import pandas as pd
import pytest

from edup.analytics.business_facts import (
    compute_business_facts,
    break_even_enrollment_change,
    revenue_scenarios,
    enrollment_reference,
)
from edup.config import (
    COURSE_CATEGORIES,
    COURSE_LEVELS,
    COURSE_TYPES,
    PAYMENT_METHODS,
)
from edup.features.features import (
    validate_course_inputs,
    price_band,
    experience_bucket,
    seasonality_label,
)


BASE = dict(
    course_category='Business', course_level='Beginner', course_price=99,
    course_duration=20, teacher_experience=5, teacher_rating=4.0,
    course_type='Paid', course_rating=4.0, payment_method='Credit Card',
)


@pytest.mark.parametrize('field', [
    'course_price', 'course_duration', 'course_rating',
    'teacher_rating', 'teacher_experience',
])
def test_bool_course_inputs_are_rejected(field):
    values = dict(BASE)
    values[field] = True
    with pytest.raises(ValueError, match='must be a number'):
        validate_course_inputs(**values)


@pytest.mark.parametrize('price,ctype,band', [
    (0, 'Free', 'Free'), (50, 'Paid', 'Budget'), (100, 'Paid', 'Standard'),
    (200, 'Paid', 'Premium'), (500, 'Paid', 'Elite'),
])
def test_validated_price_boundaries_match_band_contract(price, ctype, band):
    values = validate_course_inputs(**{**BASE, 'course_price': price, 'course_type': ctype})
    assert values['course_price'] == price
    assert price_band(values['course_price']) == band


@pytest.mark.parametrize('experience,rounded,bucket', [
    (2.4, 2, 'Junior'), (2.6, 3, 'Mid'), (5.4, 5, 'Mid'),
    (5.6, 6, 'Senior'), (10.4, 10, 'Senior'), (10.6, 11, 'Expert'),
])
def test_teacher_experience_is_rounded_before_bucketing(experience, rounded, bucket):
    values = validate_course_inputs(**{**BASE, 'teacher_experience': experience})
    assert values['teacher_experience'] == rounded
    assert experience_bucket(values['teacher_experience']) == bucket


@pytest.mark.parametrize('override', [
    {'course_category': ''}, {'course_level': ' '}, {'course_type': 'paid'},
    {'payment_method': ''},
])
def test_blank_or_case_mismatched_choices_are_rejected(override):
    with pytest.raises(ValueError):
        validate_course_inputs(**{**BASE, **override})


@pytest.mark.parametrize('quarter,label', [
    (1, 'NewYearRush'), (2, 'Spring'), (3, 'Summer'), (4, 'YearEnd'),
])
def test_seasonality_label_valid_quarters(quarter, label):
    assert seasonality_label(quarter) == label


@pytest.mark.parametrize('quarter', [0, 5, None, 1.5, True, math.nan, math.inf])
def test_seasonality_label_rejects_invalid_quarters(quarter):
    with pytest.raises(ValueError, match='Quarter'):
        seasonality_label(quarter)


def test_bool_business_calculations_are_rejected():
    pytest.importorskip('plotly')
    from app import utils

    with pytest.raises(ValueError):
        break_even_enrollment_change(True, 100)
    with pytest.raises(ValueError):
        revenue_scenarios(True, 100)
    with pytest.raises(ValueError):
        utils.calculate_expected_revenue('Paid', True, 10)
    with pytest.raises(ValueError):
        utils.calculate_expected_revenue('Paid', 100, True)


def test_zero_base_price_scenarios_do_not_divide_by_zero():
    table = revenue_scenarios(0, 100, prices=[0, 50])
    assert table['ProjectedRevenue'].tolist() == pytest.approx([0.0, 5000.0])
    assert table['PriceChangePct'].isna().all()
    assert table['BreakEvenEnrollmentChangePct'].isna().all()


def test_full_decline_and_full_double_scenario_bounds():
    declined = revenue_scenarios(100, 100, assumed_change_pct=-100, prices=[100])
    assert declined.loc[0, 'ProjectedEnrollments'] == 0
    assert declined.loc[0, 'ProjectedRevenue'] == 0

    doubled = revenue_scenarios(100, 100, assumed_change_pct=100, prices=[100])
    assert doubled.loc[0, 'ProjectedEnrollments'] == 200
    assert doubled.loc[0, 'ProjectedRevenue'] == 20000


def test_expected_revenue_paid_boundary_and_free_normalization():
    pytest.importorskip('plotly')
    from app import utils

    assert utils.calculate_expected_revenue('Paid', 500, 10) == 5000
    assert utils.calculate_expected_revenue('Free', 500, 10) == 0


def test_all_free_portfolio_has_zero_revenue_share(df):
    free = df.copy()
    free['Amount'] = 0
    facts = compute_business_facts(free)
    assert facts['paid_transactions'] == 0
    assert facts['free_transactions'] == len(free)
    assert facts['total_revenue'] == 0
    assert facts['top3_share_pct'] == 0
    assert facts['marketing_revenue'] == 0


def test_enrollment_reference_single_course_has_zero_spread():
    frame = pd.DataFrame({'CourseID': ['C1', 'C1'], 'TransactionID': ['T1', 'T2']})
    reference = enrollment_reference(frame)
    assert reference['n_courses'] == 1
    assert reference['mean'] == 2
    assert reference['std'] == 0


def test_identity_summary_detects_non_course_level_split():
    frame = pd.DataFrame({
        'CourseID': ['C1', 'C1'],
        'CourseType': ['Paid', 'Paid'],
        'CoursePrice': [100.0, 100.0],
        'Amount': [100.0, 0.0],
    })
    from edup.analytics.business_facts import amount_price_identity_summary
    summary = amount_price_identity_summary(frame)
    assert summary['identity_holds'] is True
    assert summary['mixed_courses'] == 1
    assert summary['paid_free_is_course_level'] is False