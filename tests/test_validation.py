import pandas as pd
import pytest

from quantlab.strategies import cross_sectional_momentum, ts_momentum
from quantlab.validation import param_grid, walk_forward


def test_param_grid_is_cartesian_product():
    grid = param_grid({"a": [1, 2], "b": ["x", "y", "z"]})
    assert len(grid) == 6
    assert {"a": 2, "b": "z"} in grid


def test_walk_forward_covers_only_out_of_sample_period(prices):
    wf = walk_forward(prices, ts_momentum, {"lookback": [20, 60]}, train_days=300, test_days=100)
    oos = wf.oos.net_returns
    assert oos.index[0] == prices.index[300]
    assert oos.index[-1] == prices.index[-1]
    assert len(wf.folds) == 5  # 450 OOS days / 100, last fold partial
    assert set(wf.folds["params"].map(lambda p: p["lookback"])) <= {20, 60}


def test_walk_forward_params_ignore_the_future(prices):
    """Fold k's chosen params must not change when prices after fold k change."""
    grid = {"lookback": [20, 40, 60]}
    base = walk_forward(prices, ts_momentum, grid, train_days=300, test_days=100)
    shocked = prices.copy()
    shocked.iloc[500:] *= pd.Series(range(len(shocked) - 500), index=shocked.index[500:]).add(
        1
    ).pow(0.01).to_numpy()[:, None]
    alt = walk_forward(shocked, ts_momentum, grid, train_days=300, test_days=100)
    assert base.folds["params"].iloc[:2].tolist() == alt.folds["params"].iloc[:2].tolist()


def test_walk_forward_enters_monthly_strategy_mid_month(prices):
    wf = walk_forward(
        prices, cross_sectional_momentum, {"lookback": [40, 60]},
        train_days=300, test_days=100, fixed_params={"top_n": 2},
    )
    first_day = wf.oos.weights.iloc[0]
    assert first_day.sum() == pytest.approx(1.0)


def test_walk_forward_rejects_short_history(prices):
    with pytest.raises(ValueError):
        walk_forward(prices.iloc[:100], ts_momentum, {"lookback": [20]}, train_days=80, test_days=40)
