import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = ['README.md', 'reports/executive_summary.md', 'reports/research_paper.md']


def _read(path):
    return open(os.path.join(ROOT, path), encoding='utf-8').read()


def test_docs_contain_verified_figures():
    combined = '\n'.join(_read(p) for p in DOCS)
    assert '64.03%' in combined
    assert '6,403' in combined
    assert '3,597' in combined
    assert '$202,750.67' in combined
    assert '$181,527.58' in combined
    assert '$169,103.21' in combined
    assert '60.72%' in combined
    assert '$133.38' in combined
    assert '$0.00' in combined


def test_docs_do_not_repeat_contradicted_claims():
    combined = '\n'.join(_read(p) for p in DOCS)
    assert 'approximately 50% of total transactions' not in combined
    assert '50% free enrollment rate' not in combined
    assert 'AI, ML, Data Science' not in combined
    assert 'All six models achieve an R² of 1.0' not in combined
    assert 'production-ready' not in combined.replace('not production-ready', '')


def test_readme_and_exec_describe_leakage_and_readiness():
    readme = _read('README.md')
    exec_summary = _read('reports/executive_summary.md')
    assert 'accounting identity' in readme
    assert 'does not beat a mean baseline' in readme
    assert 'not production-ready' in readme
    assert 'cached Prophet output' in exec_summary
    assert 'not production-ready' in exec_summary
