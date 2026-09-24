import numpy as np
import pandas as pd
import pytest

from quantlab.engine import run_backtest
from quantlab.metrics import drawdown, performance_summary
from quantlab.strategies import buy_and_hold


def test_buy_and_hold_single_asset_matches_price(prices):
    px = prices[["A"]]
    result = run_backtest(px, buy_and_hold(px), cost_rate=0.0)
    expected = px["A"] / px["A"].iloc[0]
    np.testing.assert_allclose(result.equity.to_numpy(), expected.to_numpy())


def test_equal_weight_buy_and_hold_drifts_without_turnover(prices):
    result = run_backtest(prices, buy_and_hold(prices), cost_rate=0.001)
    expected = (prices / prices.iloc[0]).mean(axis=1)
    np.testing.assert_allclose(result.gross_equity.to_numpy(), expected.to_numpy())
    # Only the initial purchase trades.
    assert result.turnover.iloc[0] == pytest.approx(1.0)
    assert result.turnover.iloc[1:].sum() == 0


def test_weights_act_on_next_day_return(prices):
    """A position set at close t must not earn day t's return."""
    px = prices[["A"]]
    w = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
    w.iloc[10] = 1.0
    result = run_backtest(px, w, cost_rate=0.0)
    day_ret = px["A"].pct_change()
    assert result.gross_returns.iloc[0] == 0.0          # day 10 itself
    assert result.gross_returns.iloc[1] == pytest.approx(day_ret.iloc[11])


def test_costs_scale_with_turnover(prices):
    px = prices[["A"]]
    w = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
    w.iloc[0] = 1.0
    w.iloc[5] = 0.0
    result = run_backtest(px, w, cost_rate=0.01)
    assert result.costs.sum() == pytest.approx(0.01 * (1.0 + result.turnover.iloc[5]))


def test_short_position_earns_negative_return(prices):
    px = prices[["A"]]
    w = pd.DataFrame(-1.0, index=px.index, columns=px.columns)
    result = run_backtest(px, w, cost_rate=0.0)
    day_ret = px["A"].pct_change()
    assert result.gross_returns.iloc[1] == pytest.approx(-day_ret.iloc[1])


def test_drawdown_and_summary():
    rets = pd.Series([0.1, -0.5, 0.2])
    dd = drawdown(rets)
    assert dd.min() == pytest.approx(-0.5)
    summary = performance_summary(rets)
    assert summary["total_return"] == pytest.approx(1.1 * 0.5 * 1.2 - 1)
    assert summary["max_drawdown"] == pytest.approx(-0.5)


def test_risk_free_rate_lowers_sharpe(prices):
    rets = prices["A"].pct_change().dropna()
    assert performance_summary(rets, 0.05)["sharpe"] < performance_summary(rets, 0.0)["sharpe"]
