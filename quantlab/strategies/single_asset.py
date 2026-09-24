"""Per-asset timing strategies, equal-weighted across the universe.

Ported from multi-strategy-backtesting-framework. With a single ticker they
reproduce the original behaviour; with several tickers each one gets a
1/N sleeve that is either invested or in cash.
"""

from __future__ import annotations

import pandas as pd


def _equal_sleeves(signal: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    n = prices.shape[1]
    weights = signal.astype(float) / n
    # Rows before any signal is computable stay NaN (= not started yet).
    warmup = signal.isna().all(axis=1)
    weights[warmup] = float("nan")
    return weights


def buy_and_hold(prices: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight, bought on day one and left to drift."""
    weights = pd.DataFrame(float("nan"), index=prices.index, columns=prices.columns)
    weights.iloc[0] = 1.0 / prices.shape[1]
    return weights


def ts_momentum(prices: pd.DataFrame, lookback: int = 60) -> pd.DataFrame:
    """Long an asset while its trailing ``lookback``-day return is positive."""
    mom = prices.pct_change(lookback, fill_method=None)
    signal = (mom > 0).where(mom.notna())
    return _equal_sleeves(signal, prices)


def mean_reversion(
    prices: pd.DataFrame, window: int = 20, threshold: float = 0.05
) -> pd.DataFrame:
    """Long an asset while it trades more than ``threshold`` below its SMA."""
    sma = prices.rolling(window).mean()
    distance = prices / sma - 1
    signal = (distance < -threshold).where(distance.notna())
    return _equal_sleeves(signal, prices)
