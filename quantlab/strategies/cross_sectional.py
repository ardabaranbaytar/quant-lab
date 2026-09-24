"""Cross-sectional momentum (ported from momentum-strategy-backtest)."""

from __future__ import annotations

from typing import cast

import pandas as pd


def month_end_dates(index: pd.Index) -> pd.DatetimeIndex:
    """Last *trading* day of each month present in ``index``.

    (Calendar month-ends from ``resample('ME')`` can fall on weekends and
    silently drop rebalances when reindexed onto trading days.)
    """
    dates = pd.DatetimeIndex(index)
    s = pd.Series(dates, index=dates)
    return pd.DatetimeIndex(s.groupby(dates.to_period("M")).max().to_numpy())


def cross_sectional_momentum(
    prices: pd.DataFrame,
    lookback: int = 60,
    top_n: int = 5,
    skip_days: int = 0,
    universe: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Each month-end, hold the ``top_n`` best performers equally weighted.

    ``skip_days`` excludes the most recent days from the momentum window
    (classic 12-1 momentum uses skip ~21 to avoid short-term reversal).
    ``universe`` is an optional boolean (dates x tickers) point-in-time
    membership mask; only members on the rebalance date are eligible.
    """
    mom = prices.shift(skip_days).pct_change(lookback, fill_method=None)
    weights = pd.DataFrame(float("nan"), index=prices.index, columns=prices.columns)
    if universe is not None:
        universe = universe.reindex(index=prices.index, columns=prices.columns, fill_value=False)
        # Must still be trading today: a dead stock can't be bought.
        mom = mom.where(universe & prices.notna())

    for date in month_end_dates(prices.index):
        scores = cast(pd.Series, mom.loc[date]).dropna()
        if len(scores) < top_n:
            continue
        winners = scores.nlargest(top_n).index
        row = pd.Series(0.0, index=prices.columns)
        row[winners] = 1.0 / top_n
        weights.loc[date] = row
    return weights
