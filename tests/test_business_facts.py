import math

import pytest

import business_facts as bf


def test_headline_facts_are_data_verified(df):
    facts = bf.compute_business_facts(df)
    assert facts['transactions'] == 10000
    assert facts['paid_transactions'] == 3597
    assert facts['free_transactions'] == 6403
    assert math.isclose(facts['free_share_pct'], 64.03, abs_tol=1e-9)
    assert math.isclose(facts['paid_share_pct'], 35.97, abs_tol=1e-9)
    assert math.isclose(facts['total_revenue'], 911323.47, abs_tol=0.01)
    assert facts['top3_categories'] == [
        'Artificial Intelligence', 'Business', 'Project Management']
    assert math.isclose(facts['top3_revenue']['Artificial Intelligence'], 202750.67, abs_tol=0.01)
    assert math.isclose(facts['top3_revenue']['Business'], 181527.58, abs_tol=0.01)
    assert math.isclose(facts['top3_revenue']['Project Management'], 169103.21, abs_tol=0.01)
    assert math.isclose(facts['top3_share_pct'], 60.716, abs_tol=0.01)
    assert math.isclose(facts['machine_learning_revenue'], 133.38, abs_tol=0.01)
    assert math.isclose(facts['marketing_revenue'], 0.0, abs_tol=1e-9)
    assert facts['paid_courses'] == 22
    assert facts['free_courses'] == 38


def test_quarterly_facts_do_not_support_q1_surge(df):
    facts = bf.compute_business_facts(df)
    q1 = facts['quarterly']['Q1']
    q2 = facts['quarterly']['Q2']
    assert q1['transactions'] == 2456
    assert q2['transactions'] == 2555
    assert math.isclose(q1['revenue'], 231643.16, abs_tol=0.01)
    assert math.isclose(q2['revenue'], 231406.06, abs_tol=0.01)
    assert q2['transactions'] > q1['transactions']


def test_amount_price_identity_and_course_level_split(df):
    summary = bf.amount_price_identity_summary(df)
    assert summary['identity_holds'] is True
    assert summary['paid_free_is_course_level'] is True
    assert summary['paid_mismatches'] == 0
    assert summary['free_mismatches'] == 0
    assert summary['mixed_courses'] == 0
    assert math.isclose(summary['amount_price_correlation'], 1.0, abs_tol=1e-9)


def test_enrollment_reference_distribution(df):
    ref = bf.enrollment_reference(df)
    assert ref['n_courses'] == 60
    assert math.isclose(ref['mean'], 166.6667, abs_tol=0.01)
    assert math.isclose(ref['median'], 166.0, abs_tol=0.5)
    assert ref['min'] == 140
    assert ref['max'] == 196
    assert ref['p10'] < ref['mean'] < ref['p90']


def test_price_demand_is_not_identifiable(df):
    diag = bf.price_demand_diagnostics(df)
    assert diag['n_paid_courses'] == 22
    assert diag['unique_paid_prices'] == 22
    assert diag['courses_with_multiple_prices'] == 0
    assert math.isclose(diag['paid_price_enrollment_corr'], -0.0217, abs_tol=0.001)
    assert diag['elasticity_identifiable'] is False
    assert 'cannot be estimated' in diag['reason']


def test_break_even_enrollment_change():
    assert math.isclose(bf.break_even_enrollment_change(100, 110), -9.0909, abs_tol=0.001)
    assert math.isclose(bf.break_even_enrollment_change(100, 125), -20.0, abs_tol=1e-9)
    assert math.isclose(bf.break_even_enrollment_change(100, 50), 100.0, abs_tol=1e-9)
    assert math.isnan(bf.break_even_enrollment_change(0, 100))
    assert math.isnan(bf.break_even_enrollment_change(100, 0))


def test_revenue_scenarios_are_explicit_arithmetic():
    table = bf.revenue_scenarios(100, 100, assumed_change_pct=10, prices=[50, 100, 150])
    assert list(table['Price']) == [50, 100, 150]
    assert table['ProjectedEnrollments'].tolist() == pytest.approx([110, 110, 110])
    assert table['ProjectedRevenue'].tolist() == pytest.approx([5500, 11000, 16500])
    assert math.isclose(table.loc[1, 'BreakEvenEnrollmentChangePct'], 0.0)
    assert math.isclose(table.loc[2, 'BreakEvenEnrollmentChangePct'], -33.3333, abs_tol=0.001)


@pytest.mark.parametrize('price', [-1, 500.01])
def test_revenue_scenarios_reject_out_of_range_prices(price):
    with pytest.raises(ValueError):
        bf.revenue_scenarios(100, 100, prices=[price])


def test_revenue_scenarios_reject_bad_assumption():
    with pytest.raises(ValueError):
        bf.revenue_scenarios(100, 100, assumed_change_pct=101)
    with pytest.raises(ValueError):
        bf.revenue_scenarios(100, -1)
