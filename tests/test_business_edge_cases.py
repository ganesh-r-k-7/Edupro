import pandas as pd
import pytest

import business_facts as bf


COLUMNS = ['TransactionID', 'TransactionDate', 'CourseID', 'CourseCategory',
           'CourseType', 'CoursePrice', 'Amount']


def _empty():
    return pd.DataFrame(columns=COLUMNS)


def test_empty_facts_return_zeroed_summary():
    facts = bf.compute_business_facts(_empty())
    assert facts['transactions'] == 0
    assert facts['total_revenue'] == 0.0
    assert facts['top3_categories'] == []
    assert facts['top3_share_pct'] == 0.0
    assert facts['date_min'] is None
    assert facts['quarterly']['Q1']['transactions'] == 0


def test_facts_fail_on_missing_columns():
    with pytest.raises(ValueError, match='Missing required columns'):
        bf.compute_business_facts(_empty().drop(columns=['Amount']))


def test_empty_identity_summary_is_safe():
    summary = bf.amount_price_identity_summary(_empty())
    assert summary['paid_rows'] == 0
    assert summary['free_rows'] == 0
    assert summary['mixed_courses'] == 0
    assert summary['amount_price_correlation'] is None
    assert summary['identity_holds'] is True


def test_empty_enrollment_reference_is_safe():
    ref = bf.enrollment_reference(pd.DataFrame(columns=['CourseID', 'TransactionID']))
    assert ref['n_courses'] == 0
    assert ref['mean'] == 0.0
    assert ref['p90'] == 0.0


def test_empty_price_diagnostics_are_safe():
    diag = bf.price_demand_diagnostics(_empty().assign(TransactionID=[]))
    assert diag['n_courses'] == 0
    assert diag['n_paid_courses'] == 0
    assert diag['unique_paid_prices'] == 0
    assert diag['paid_price_enrollment_corr'] is None
    assert diag['all_price_enrollment_corr'] is None
    assert diag['elasticity_identifiable'] is False
