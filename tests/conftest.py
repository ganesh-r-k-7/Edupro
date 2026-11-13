import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


@pytest.fixture(scope='session')
def data_path():
    return os.path.join(ROOT, 'data', 'processed_data.csv')


@pytest.fixture(scope='session')
def df(data_path):
    return pd.read_csv(data_path, parse_dates=['TransactionDate'])
