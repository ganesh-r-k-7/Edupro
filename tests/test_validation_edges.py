import math

import pytest

import business_facts as bf
import feature_contract as fc


BASE = dict(
    course_category='Business', course_level='Beginner', course_price=99,
    course_duration=20, teacher_experience=5, teacher_rating=4.0,
    course_type='Paid', course_rating=4.0, payment_method='Credit Card',
)


@pytest.mark.parametrize('field,value', [
    ('course_price', math.nan), ('course_price', math.inf), ('course_price', None),
    ('course_price', 'abc'), ('course_duration', math.nan), ('course_duration', math.inf),
    ('course_duration', None), ('course_rating', math.nan), ('course_rating', math.inf),
    ('teacher_rating', math.nan), ('teacher_rating', math.inf),
    ('teacher_experience', math.nan), ('teacher_experience', math.inf),
])
def test_non_finite_or_non_numeric_inputs_are_rejected(field, value):
    values = dict(BASE)
    values[field] = value
    with pytest.raises(ValueError):
        fc.validate_course_inputs(**values)


@pytest.mark.parametrize('override', [
    {'course_category': 'Nope'},
    {'course_level': 'Nope'},
    {'course_type': 'Nope'},
    {'payment_method': 'Cash'},
    {'course_price': -1},
    {'course_price': 500.01},
    {'course_duration': 0},
    {'course_duration': 200.01},
    {'course_rating': 0.99},
    {'course_rating': 5.01},
    {'teacher_rating': 0.99},
    {'teacher_rating': 5.01},
    {'teacher_experience': -1},
    {'teacher_experience': 31},
])
def test_out_of_contract_inputs_are_rejected(override):
    values = dict(BASE)
    values.update(override)
    with pytest.raises(ValueError):
        fc.validate_course_inputs(**values)


def test_free_course_normalizes_only_price():
    values = fc.validate_course_inputs(**{**BASE, 'course_type': 'Free', 'course_price': 99})
    assert values['course_price'] == 0
    assert values['course_rating'] == 4.0
    assert values['payment_method'] == 'Credit Card'


@pytest.mark.parametrize('price', [-1, 500.01, math.nan, math.inf])
def test_free_course_still_rejects_invalid_price(price):
    with pytest.raises(ValueError):
        fc.validate_course_inputs(**{**BASE, 'course_type': 'Free', 'course_price': price})


def test_encode_course_level_rejects_unknown_value():
    with pytest.raises(ValueError, match='Course level'):
        fc.encode_course_level('Expert')


@pytest.mark.parametrize('price,enrollments,match', [
    (math.nan, 10, 'finite'),
    (math.inf, 10, 'finite'),
    (100, math.nan, 'finite'),
    (100, math.inf, 'finite'),
    (500.01, 10, 'between'),
    (100, -1, 'negative'),
])
def test_expected_revenue_rejects_invalid_values(price, enrollments, match):
    pytest.importorskip('plotly')
    from app import utils

    with pytest.raises(ValueError, match=match):
        utils.calculate_expected_revenue('Paid', price, enrollments)


@pytest.mark.parametrize('kwargs,match', [
    ({'base_price': math.nan}, 'base_price'),
    ({'base_price': math.inf}, 'base_price'),
    ({'reference_enrollments': math.nan}, 'reference_enrollments'),
    ({'reference_enrollments': math.inf}, 'reference_enrollments'),
    ({'assumed_change_pct': math.nan}, 'assumed_change_pct'),
    ({'assumed_change_pct': math.inf}, 'assumed_change_pct'),
    ({'prices': [math.nan]}, 'Scenario price'),
    ({'prices': [math.inf]}, 'Scenario price'),
    ({'prices': []}, 'At least one'),
])
def test_scenarios_reject_invalid_values(kwargs, match):
    values = {'base_price': 100, 'reference_enrollments': 100}
    values.update(kwargs)
    with pytest.raises(ValueError, match=match):
        bf.revenue_scenarios(**values)


def test_break_even_rejects_non_finite_values():
    with pytest.raises(ValueError):
        bf.break_even_enrollment_change(math.nan, 100)
    with pytest.raises(ValueError):
        bf.break_even_enrollment_change(100, math.inf)
