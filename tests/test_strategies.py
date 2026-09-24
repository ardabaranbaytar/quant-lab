import numpy as np
import pandas as pd
import pytest

from quantlab.engine import run_backtest
from quantlab.strategies import (
    STRATEGIES,
    cross_sectional_momentum,
    mean_reversion,
    pairs_trading,
    ts_momentum,
)


def _assert_no_lookahead(strategy, prices, **params):
    """Changing future prices must not change today's weights."""
    cut = 400
    full = strategy(prices, **params)
    shocked = prices.copy()
    shocked.iloc[cut + 1 :] *= 1.5
    altered = strategy(shocked, **params)
    pd.testing.assert_frame_equal(full.iloc[: cut + 1], altered.iloc[: cut + 1])


@pytest.mark.parametrize(
    "strategy,params",
    [
        (ts_momentum, {"lookback": 60}),
        (mean_reversion, {"window": 20, "threshold": 0.05}),
        (cross_sectional_momentum, {"lookback": 60, "top_n": 2}),
    ],
)
def test_strategies_have_no_lookahead(prices, strategy, params):
    _assert_no_lookahead(strategy, prices, **params)


def test_pairs_has_no_lookahead(cointegrated_pair):
    _assert_no_lookahead(pairs_trading, cointegrated_pair, hedge_window=120, z_window=60)


def test_every_strategy_runs_through_engine(prices):
    params = {"cross_sectional_momentum": {"top_n": 2}}
    for name, fn in STRATEGIES.items():
        result = run_backtest(prices, fn(prices, **params.get(name, {})))
        assert len(result.net_returns) > 0, name
        assert np.isfinite(result.equity.iloc[-1]), name


def test_engine_rejects_strategy_without_positions(prices):
    with pytest.raises(ValueError, match="never produced a position"):
        run_backtest(prices, cross_sectional_momentum(prices, top_n=10))


def test_ts_momentum_weights_are_equal_sleeves(prices):
    w = ts_momentum(prices, lookback=60).dropna(how="all")
    assert set(np.unique(w.to_numpy())) <= {0.0, 0.25}


def test_cross_sectional_rebalances_monthly_on_trading_days(prices):
    w = cross_sectional_momentum(prices, lookback=60, top_n=2)
    rebalance_rows = w.dropna(how="all")
    assert rebalance_rows.index.isin(prices.index).all()
    assert rebalance_rows.index.to_period("M").is_unique
    np.testing.assert_allclose(rebalance_rows.sum(axis=1), 1.0)


def test_pairs_profits_on_cointegrated_data(cointegrated_pair):
    w = pairs_trading(cointegrated_pair, hedge_window=120, z_window=60)
    active = w.dropna(how="all")
    gross = active.abs().sum(axis=1)
    assert ((gross == 0) | np.isclose(gross, 1.0)).all()
    # Legs have opposite signs whenever in a trade.
    in_trade = active[gross > 0]
    assert (np.sign(in_trade["A"]) == -np.sign(in_trade["B"])).all()
    result = run_backtest(cointegrated_pair, w, cost_rate=0.0005)
    assert result.equity.iloc[-1] > 1.0
