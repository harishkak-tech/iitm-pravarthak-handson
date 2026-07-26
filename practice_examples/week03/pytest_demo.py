"""pytest_demo.py — Week 3 practice. Distilled from the SHAPE of tests/test_pipeline.py
& tests/test_api.py (functions named test_*, plain `assert`). Feel the pytest minimum
shape in isolation — no app, no mocking.
Run:  python -m pytest practice_examples/week03/pytest_demo.py -v
In case of import error Run : pip install --break-system-packages pytest pytest-asyncio "httpx>=0.27,<0.28"
"""

def add(a, b):                       # a tiny pure function to test
    return a + b


def test_add_positive():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-1, -1) == -2


def test_add_zero():                 # change 4 -> 5 to SEE a red failure, then change back
    assert add(2, 2) == 5
