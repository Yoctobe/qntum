import pytest

from test_simulator import build_macro_engine


@pytest.fixture
def engine():
    return build_macro_engine()


@pytest.fixture
def baseline(engine):
    return engine.simulate(horizon=8, n_bootstrap=50)
