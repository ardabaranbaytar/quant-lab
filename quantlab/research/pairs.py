"""Pair selection: correlation, Engle-Granger cointegration, half-life."""

from __future__ import annotations

from collections.abc import Iterable
from itertools import combinations

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint


def half_life(spread: pd.Series) -> float:
    """Mean-reversion half-life (days) from an AR(1) fit on spread changes."""
    s = spread.dropna()
    lagged = s.shift(1).iloc[1:]
    delta = s.diff().iloc[1:]
    x = lagged - lagged.mean()
    slope = float((x * (delta - delta.mean())).sum() / (x**2).sum())
    return float(-np.log(2) / slope) if slope < 0 else np.inf


def scan_pairs(
    prices: pd.DataFrame,
    pairs: Iterable[tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """Rank candidate pairs by cointegration p-value.

    If ``pairs`` is None every combination of columns is tested. Use only
    in-sample data here, then trade the chosen pairs out-of-sample.
    """
    pairs = list(pairs) if pairs is not None else list(combinations(prices.columns, 2))
    rows = []
    for a, b in pairs:
        px = prices[[a, b]].dropna()
        if len(px) < 100:
            continue
        rets = px.pct_change().dropna()
        _, p_value, _ = coint(px[a], px[b])
        beta = np.polyfit(px[b], px[a], 1)[0]
        rows.append(
            {
                "pair": f"{a}-{b}",
                "asset_a": a,
                "asset_b": b,
                "correlation": float(rets[a].corr(rets[b])),
                "coint_pvalue": float(p_value),
                "hedge_ratio": float(beta),
                "half_life": half_life(px[a] - beta * px[b]),
            }
        )
    return pd.DataFrame(rows).sort_values("coint_pvalue").reset_index(drop=True)
