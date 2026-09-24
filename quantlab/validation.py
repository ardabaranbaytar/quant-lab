"""Walk-forward validation.

Parameters are chosen on a trailing training window and then used, untouched,
on the following test window. The out-of-sample (OOS) test segments are
stitched into one continuous backtest, so the reported performance never
benefits from parameters picked with hindsight.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np
import pandas as pd

from quantlab.engine import BacktestResult, run_backtest
from quantlab.metrics import performance_summary


@dataclass
class WalkForwardResult:
    oos: BacktestResult
    folds: pd.DataFrame  # one row per fold: dates, chosen params, train/test score


def param_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(grid)
    return [dict(zip(keys, values)) for values in product(*grid.values())]


def _score(result: BacktestResult, metric: str) -> float:
    try:
        value = performance_summary(result.net_returns)[metric]
    except ValueError:
        return -np.inf
    return value if np.isfinite(value) else -np.inf


def walk_forward(
    prices: pd.DataFrame,
    strategy: Callable[..., pd.DataFrame],
    grid: dict[str, list[Any]],
    train_days: int = 756,
    test_days: int = 126,
    cost_rate: float = 0.001,
    metric: str = "sharpe",
    fixed_params: dict[str, Any] | None = None,
) -> WalkForwardResult:
    """Rolling walk-forward optimisation of ``strategy`` over ``grid``.

    Strategies are causal, so weights for a window are computed on all prices
    up to the window's end (which provides indicator warm-up) and then sliced.
    """
    fixed_params = fixed_params or {}
    candidates = param_grid(grid)
    idx = prices.index
    if len(idx) < train_days + test_days:
        raise ValueError("Not enough history for one train + test fold.")

    oos_weights = []
    folds = []
    start = train_days
    while start < len(idx):
        end = min(start + test_days, len(idx))
        train_idx = idx[start - train_days : start]
        test_idx = idx[start:end]

        best_params, best_score = None, -np.inf
        for params in candidates:
            weights = strategy(prices.loc[: train_idx[-1]], **fixed_params, **params)
            try:
                res = run_backtest(prices.loc[train_idx], weights.loc[train_idx], cost_rate)
            except ValueError:
                continue
            score = _score(res, metric)
            if score > best_score:
                best_params, best_score = params, score

        if best_params is None:
            best_params = candidates[0]
        weights = strategy(prices.loc[: test_idx[-1]], **fixed_params, **best_params)
        test_weights = weights.loc[test_idx].copy()
        # Enter the fold holding what the chosen parameters would currently
        # hold, instead of inheriting the previous fold's book.
        if test_weights.iloc[0].isna().all():
            last_target = weights.loc[: test_idx[0]].dropna(how="all")
            if not last_target.empty:
                test_weights.iloc[0] = last_target.iloc[-1].fillna(0.0)
        oos_weights.append(test_weights)
        folds.append(
            {
                "train_start": train_idx[0].date(),
                "test_start": test_idx[0].date(),
                "test_end": test_idx[-1].date(),
                "params": best_params,
                f"train_{metric}": best_score,
            }
        )
        start = end

    stitched = pd.concat(oos_weights)
    oos_prices = prices.loc[stitched.index]
    oos = run_backtest(oos_prices, stitched, cost_rate)
    fold_df = pd.DataFrame(folds)
    fold_df[f"test_{metric}"] = [
        _score_slice(oos, row.test_start, row.test_end, metric) for row in fold_df.itertuples()
    ]
    return WalkForwardResult(oos=oos, folds=fold_df)


def _score_slice(result: BacktestResult, start, end, metric: str) -> float:
    rets = result.net_returns.loc[str(start) : str(end)]
    if len(rets) < 2:
        return np.nan
    return performance_summary(rets)[metric]
