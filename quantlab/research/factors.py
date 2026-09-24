"""Cross-sectional factor research (ported from equity-factor-research).

All factor/target frames are wide: dates x tickers.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


def momentum(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    return prices.pct_change(window, fill_method=None)


def volatility(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    return prices.pct_change(fill_method=None).rolling(window).std()


def forward_returns(prices: pd.DataFrame, horizon: int = 20) -> pd.DataFrame:
    """Return from t to t+horizon. Research target only — never a signal input."""
    return prices.shift(-horizon) / prices - 1


def information_coefficient(
    factor: pd.DataFrame, target: pd.DataFrame, method: str = "spearman"
) -> pd.Series:
    """Per-date cross-sectional correlation between factor and target.

    Spearman (rank) IC is the industry default: robust to outliers.
    """
    factor, target = factor.align(target, join="inner")
    both = factor.notna() & target.notna()
    f = factor.where(both)
    y = target.where(both)
    if method == "spearman":
        f = f.rank(axis=1)
        y = y.rank(axis=1)
    f = f.sub(f.mean(axis=1), axis=0)
    y = y.sub(y.mean(axis=1), axis=0)
    num = (f * y).sum(axis=1)
    den = cast(pd.Series, np.sqrt((f**2).sum(axis=1) * (y**2).sum(axis=1)))
    ic = num / den.replace(0, np.nan)
    return ic[both.sum(axis=1) >= 3].rename("ic")


def ic_summary(ic: pd.Series) -> dict[str, float]:
    ic = ic.dropna()
    mean, std = ic.mean(), ic.std()
    return {
        "mean_ic": float(mean),
        "std_ic": float(std),
        "ic_ir": float(mean / std) if std > 0 else np.nan,
        "t_stat": float(mean / std * np.sqrt(len(ic))) if std > 0 else np.nan,
        "pct_positive": float((ic > 0).mean()),
    }


def quantile_returns(
    factor: pd.DataFrame, target: pd.DataFrame, n_quantiles: int = 5
) -> pd.DataFrame:
    """Mean target return per factor quantile, per date (dates x quantiles).

    Quantile 1 = lowest factor values. ``result[n] - result[1]`` is the
    long-short spread time series.
    """
    factor, target = factor.align(target, join="inner")
    ranks = factor.rank(axis=1, pct=True)
    buckets = cast(pd.DataFrame, np.ceil(ranks * n_quantiles)).clip(1, n_quantiles)

    stacked = pd.DataFrame(
        {"bucket": buckets.stack(future_stack=True), "target": target.stack(future_stack=True)}
    ).dropna()
    means = stacked.groupby([stacked.index.get_level_values(0), "bucket"])["target"].mean()
    table = means.unstack("bucket")
    table.columns = table.columns.astype(int)
    return table
