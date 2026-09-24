import numpy as np
import pandas as pd
import pytest

from quantlab.research import (
    forward_returns,
    information_coefficient,
    momentum,
    quantile_returns,
    scan_pairs,
)
from quantlab.research.factors import ic_summary
from quantlab.research.pairs import half_life


def test_perfect_factor_has_ic_one(prices):
    target = forward_returns(prices, 20)
    ic = information_coefficient(target, target)
    assert ic.dropna().min() == pytest.approx(1.0)


def test_quantile_returns_are_monotonic_for_perfect_factor(prices):
    target = forward_returns(prices, 20)
    q = quantile_returns(target, target, n_quantiles=4).mean()
    assert q.is_monotonic_increasing


def test_ic_summary_on_random_factor_is_near_zero(prices):
    rng = np.random.default_rng(0)
    noise = pd.DataFrame(rng.normal(size=prices.shape), index=prices.index, columns=prices.columns)
    stats = ic_summary(information_coefficient(noise, forward_returns(prices, 20)))
    assert abs(stats["mean_ic"]) < 0.1


def test_momentum_uses_past_only(prices):
    mom = momentum(prices, 20)
    assert mom.iloc[:20].isna().all().all()
    assert mom.iloc[20, 0] == pytest.approx(prices.iloc[20, 0] / prices.iloc[0, 0] - 1)


def test_scan_pairs_finds_cointegration(cointegrated_pair, prices):
    data = cointegrated_pair.join(prices[["C"]].reindex(cointegrated_pair.index).ffill().bfill())
    result = scan_pairs(data)
    assert result.iloc[0]["pair"] == "A-B"
    assert result.iloc[0]["coint_pvalue"] < 0.05
    assert result.iloc[0]["hedge_ratio"] == pytest.approx(2.0, abs=0.2)


def test_half_life_of_ar1():
    rng = np.random.default_rng(1)
    x = np.zeros(5000)
    for t in range(1, len(x)):
        x[t] = 0.9 * x[t - 1] + rng.normal()
    assert half_life(pd.Series(x)) == pytest.approx(np.log(2) / 0.1, rel=0.2)
