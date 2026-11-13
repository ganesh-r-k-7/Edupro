import os
import re

import business_facts as bf


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_app_has_no_optimal_price_or_idxmax_logic():
    source = open(os.path.join(ROOT, 'app', 'app.py'), encoding='utf-8').read()
    assert not re.search(r'optimal', source, re.IGNORECASE)
    assert 'idxmax' not in source
    assert 'Price Scenario Analysis' in source
    assert 'No price is recommended' in source


def test_scenario_changes_with_assumption():
    unchanged = bf.revenue_scenarios(100, 100, assumed_change_pct=0, prices=[100, 200])
    reduced = bf.revenue_scenarios(100, 100, assumed_change_pct=-20, prices=[100, 200])
    assert unchanged.loc[1, 'ProjectedRevenue'] == 20000
    assert reduced.loc[1, 'ProjectedRevenue'] == 16000
    assert unchanged.loc[1, 'ProjectedEnrollments'] == 100
    assert reduced.loc[1, 'ProjectedEnrollments'] == 80


def test_scenario_has_break_even_but_no_recommendation():
    table = bf.revenue_scenarios(100, 100, assumed_change_pct=0, prices=[100, 110, 125])
    assert 'BreakEvenEnrollmentChangePct' in table.columns
    assert not any('optimal' in c.lower() for c in table.columns)
    assert not any('recommend' in c.lower() for c in table.columns)
