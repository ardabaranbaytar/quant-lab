import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def prices() -> pd.DataFrame:
    """Deterministic random-walk prices for 4 tickers over ~3 years."""
    rng = np.random.default_rng(42)
    idx = pd.bdate_range("2020-01-01", periods=750)
    rets = rng.normal(0.0004, 0.015, size=(len(idx), 4))
    return pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=idx, columns=list("ABCD"))


@pytest.fixture
def cointegrated_pair() -> pd.DataFrame:
    """B is a random walk; A = 2*B + stationary AR(1) noise."""
    rng = np.random.default_rng(7)
    n = 1000
    idx = pd.bdate_range("2019-01-01", periods=n)
    b = 50 + np.cumsum(rng.normal(0, 0.5, n))
    noise = np.zeros(n)
    for t in range(1, n):
        noise[t] = 0.9 * noise[t - 1] + rng.normal(0, 1.0)
    a = 2 * b + 10 + noise
    return pd.DataFrame({"A": a, "B": b}, index=idx)
