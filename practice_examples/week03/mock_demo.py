"""mock_demo.py — Week 3 practice. Distilled from tests/test_pipeline.py (lines 37-45):
"mock the boundary you don't control". We mock an EXPENSIVE call and test the code
that wraps it — without ever running the real thing.
Run:  python -m pytest practice_examples/week03/pytest_demo.py -v
In case of import error Run : pip install --break-system-packages pytest pytest-asyncio "httpx>=0.27,<0.28"
"""
import sys
from unittest.mock import patch


def expensive_call(x):               # pretend this is the LLM / an external service
    raise RuntimeError("real service — must NEVER run in a test!")


def double_it(x):                    # the code we actually want to test
    return expensive_call(x) * 2


_THIS = sys.modules[__name__]        # robust reference to this module for patching


def test_double_it_mocks_the_boundary():
    # swap the real expensive_call for a fake returning 10 — just for this test
    with patch.object(_THIS, "expensive_call", return_value=10) as m:
        result = double_it(5)
    assert result == 20              # our code doubled the fake's 10
    assert m.call_count == 1         # and hit the boundary exactly once
