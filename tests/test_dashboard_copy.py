import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path):
    return open(os.path.join(ROOT, path), encoding='utf-8').read()


def test_dashboard_does_not_claim_profit_or_ytd_metrics():
    source = _read('app/app.py')
    assert not re.search(r'profitab', source, re.IGNORECASE)
    assert not re.search(r'\bYTD\b', source)
    assert 'Revenue Efficiency' in source
    assert 'First-to-Last Month Revenue Growth' in source
    assert 'not a learner conversion rate' in source


def test_dashboard_does_not_hide_warnings_globally():
    assert 'warnings.filterwarnings' not in _read('app/app.py')
    assert 'warnings.filterwarnings' not in _read('app/utils.py')


def test_executive_summary_matches_dashboard_labels():
    summary = _read('reports/executive_summary.md')
    assert 'profitability' not in summary.lower()
    assert 'revenue efficiency' in summary.lower()


def test_readme_matches_dashboard_capabilities():
    readme = _read('README.md').lower()
    assert 'profitability matrix' not in readme
    assert 'interactive form to predict revenue' not in readme
    assert 'not a personalized prediction' in readme
    assert 'no cost or profit data' in readme
    assert 'cached unbacktested' in readme
