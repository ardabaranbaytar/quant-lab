"""Causal break detectors for a pair (A, B).

Each detector turns prices into a daily score where *higher = more evidence
the relationship is broken*. All use information up to and including day t.
They are deliberately scale-free (t-stats, ratios, correlations) so thresholds
calibrated on one pair transfer to others.

Detector            what it sees
------------------  ----------------------------------------------------------
df_tstat            rolling Dickey-Fuller t-stat of the spread: near 0 means the
                    spread no longer mean-reverts (random walk)
half_life           rolling AR(1) half-life of the spread, in days (info only)
cusum               two-sided CUSUM of |z| beyond 2: a *persistent* excursion
                    accumulates, a quick spike that reverts does not
z_persistence       share of the last 20 days with |z| > 3
corr_drop           long-run minus short-run return correlation
divergence          |60-day change of log(A/B)| relative to its normal range
idio_vol_spike      short/long volatility of the pair's residual returns
                    (market-neutral: a sector-wide vol spike doesn't trigger it)
trend_tstat         |t-stat| of the mean daily change of log(A/B) over 40 days:
                    a steady one-way slide (a dying company) scores high, a
                    single jump that later reverts does not
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

# Voting detectors. `half_life` is reported but does not vote: it comes from
# the same regression as `df_tstat` and is too noisy on a 6-month window.
DETECTORS = [
    "df_tstat",
    "cusum",
    "z_persistence",
    "corr_drop",
    "divergence",
    "idio_vol_spike",
    "trend_tstat",
]


def lagged_hedge_ratio(
    pa: pd.Series, pb: pd.Series, window: int = 756, lag: int = 21, min_periods: int = 252
) -> pd.Series:
    """OLS beta of A on B, estimated on a window ending ``lag`` days ago.

    The lag stops the hedge ratio from quietly adapting to a break and hiding it.
    A long (3-year) window matters: spreads are autocorrelated, so a 1-year OLS
    beta is so noisy that even a truly stable pair looks non-stationary
    (see reports/break_lab.md). Adaptive filters (Kalman) have the opposite
    problem — they absorb a real break into the hedge ratio.
    """
    beta = pa.rolling(window, min_periods=min_periods).cov(pb) / pb.rolling(
        window, min_periods=min_periods
    ).var()
    return beta.shift(lag)


def rolling_dickey_fuller(spread: pd.Series, window: int = 126) -> tuple[pd.Series, pd.Series]:
    """Vectorised rolling DF regression  Δs_t = a + γ s_{t-1} + e_t.

    Returns (t-stat of γ, implied half-life in days).
    """
    x = spread.shift(1)
    y = spread.diff()
    n = window
    var_x = x.rolling(n).var()
    cov_xy = y.rolling(n).cov(x)
    var_y = y.rolling(n).var()
    gamma = cov_xy / var_x
    resid_var = ((var_y - gamma * cov_xy) * (n - 1) / (n - 2)).clip(lower=1e-12)
    se = np.sqrt(resid_var / ((n - 1) * var_x))
    tstat: pd.Series = gamma / se
    with np.errstate(divide="ignore", invalid="ignore"):
        hl = -np.log(2) / np.log1p(gamma)
    hl = hl.where((gamma < 0) & (gamma > -1), np.inf)
    return tstat, hl


def cusum(z: pd.Series, k: float = 2.0, cap: float = 500.0) -> pd.Series:
    """Two-sided Page CUSUM on a standardised series.

    The classic k=0.5 assumes independent observations; a spread z-score is
    strongly autocorrelated, so ordinary excursions would pile up. Only the
    part of |z| beyond ``k`` accumulates.
    """
    pos = neg = 0.0
    out = np.full(len(z), np.nan)
    for i, v in enumerate(z.to_numpy()):
        if np.isnan(v):
            continue
        pos = min(max(0.0, pos + v - k), cap)
        neg = min(max(0.0, neg - v - k), cap)
        out[i] = max(pos, neg)
    return pd.Series(out, index=z.index)


def compute_detectors(
    pa: pd.Series,
    pb: pd.Series,
    hedge_window: int = 756,
    df_window: int = 126,
    z_window: int = 252,
) -> pd.DataFrame:
    """All detector scores for the pair, dates x DETECTORS (+ helper columns)."""
    beta = lagged_hedge_ratio(pa, pb, hedge_window)
    spread = pa - beta * pb

    tstat, hl = rolling_dickey_fuller(spread, df_window)

    # z against a baseline that ends yesterday, so today's move can't hide itself.
    base_mean = spread.rolling(z_window).mean().shift(1)
    base_std = spread.rolling(z_window).std().shift(1)
    z = (spread - base_mean) / base_std

    ra = pa.pct_change(fill_method=None)
    rb = pb.pct_change(fill_method=None)
    corr_long = ra.rolling(252).corr(rb).shift(21)
    corr_short = ra.rolling(60).corr(rb)

    log_ratio = cast(pd.Series, np.log(pa / pb))
    move = log_ratio.diff(60)
    typical = move.abs().rolling(504, min_periods=252).median().shift(60)

    ret_beta = (ra.rolling(252).cov(rb) / rb.rolling(252).var()).shift(21)
    resid = ra - ret_beta * rb
    idio_ratio = resid.rolling(20).std() / resid.rolling(252).std().shift(21)

    dlr = log_ratio.diff()
    trend = (dlr.rolling(40).mean() / dlr.rolling(40).std() * np.sqrt(40)).abs()

    return pd.DataFrame(
        {
            "df_tstat": tstat,
            "half_life": hl.clip(upper=1000),
            "cusum": cusum(z),
            "z_persistence": (z.abs() > 3).astype(float).where(z.notna()).rolling(20).mean(),
            "corr_drop": corr_long - corr_short,
            "divergence": move.abs() / typical,
            "idio_vol_spike": idio_ratio,
            "trend_tstat": trend,
            "z": z,
            "spread": spread,
        }
    )
