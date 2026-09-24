"""Pairs trading on a cointegrated pair (ported from pairs-trading-backtest).

Fixes the look-ahead in the original notebook: the hedge ratio is estimated on
a *rolling* window of past prices instead of the full sample, and it is frozen
for the life of each trade.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.risk.monitor import BROKEN, NORMAL, WARNING


def rolling_hedge_ratio(a: pd.Series, b: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """OLS slope of a on b over a trailing window (uses data up to and incl. t)."""
    mp = min(window, 252) if min_periods is None else min_periods
    cov = a.rolling(window, min_periods=mp).cov(b)
    var = b.rolling(window, min_periods=mp).var()
    return cov / var


def pairs_trading(
    prices: pd.DataFrame,
    asset_a: str | None = None,
    asset_b: str | None = None,
    hedge_window: int = 756,
    z_window: int = 90,
    entry_z: float = 2.0,
    exit_z: float = 0.0,
    stop_z: float | None = None,
    break_monitor=None,
) -> pd.DataFrame:
    """Long/short the spread ``A - beta * B`` when its z-score is stretched.

    z > +entry  -> short spread (short A, long B)
    z < -entry  -> long spread  (long A, short B)
    exit when z crosses ``exit_z``; optional stop when |z| exceeds ``stop_z``
    (after a stop, no re-entry until |z| is back inside ``entry_z``).

    ``break_monitor`` (a :class:`quantlab.risk.BreakMonitor`) adds the risk
    layer: WARNING blocks new entries, BROKEN forces an exit and blocks the
    pair until the monitor re-enables it.

    Legs are sized so gross exposure is 100% of NAV.
    """
    asset_a = asset_a or prices.columns[0]
    asset_b = asset_b or prices.columns[1]
    pa, pb = prices[asset_a], prices[asset_b]

    beta = rolling_hedge_ratio(pa, pb, hedge_window)
    spread = pa - beta * pb
    z = (spread - spread.rolling(z_window).mean()) / spread.rolling(z_window).std()

    z_arr, beta_arr = z.to_numpy(), beta.to_numpy()
    pa_arr, pb_arr = pa.to_numpy(), pb.to_numpy()
    n = len(prices)
    w_a = np.full(n, np.nan)
    w_b = np.full(n, np.nan)

    if break_monitor is not None:
        risk_state = break_monitor.evaluate_pair(pa, pb)["state"].to_numpy()
    else:
        risk_state = np.full(n, NORMAL)

    pos, trade_beta = 0, np.nan
    armed = True  # False after a stop until z re-enters the entry band
    started = False
    for t in range(n):
        zt = z_arr[t]
        if np.isnan(zt) or np.isnan(beta_arr[t]):
            continue
        started = True
        if abs(zt) < entry_z:
            armed = True
        state = risk_state[t]

        if pos != 0 and state == BROKEN:
            pos, trade_beta = 0, np.nan
        elif pos == 0:
            can_enter = armed and state not in (BROKEN, WARNING)
            if can_enter and zt > entry_z:
                pos, trade_beta = -1, beta_arr[t]
            elif can_enter and zt < -entry_z:
                pos, trade_beta = 1, beta_arr[t]
        else:
            stopped = stop_z is not None and abs(zt) > stop_z
            reverted = (pos == 1 and zt >= -exit_z) or (pos == -1 and zt <= exit_z)
            if stopped:
                armed = False
            if stopped or reverted:
                pos, trade_beta = 0, np.nan

        if pos == 0:
            w_a[t], w_b[t] = 0.0, 0.0
        else:
            leg_a = pa_arr[t]
            leg_b = abs(trade_beta) * pb_arr[t]
            gross = leg_a + leg_b
            w_a[t] = pos * leg_a / gross
            w_b[t] = -pos * np.sign(trade_beta) * leg_b / gross

    weights = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    if started:
        weights[asset_a] = w_a
        weights[asset_b] = w_b
        active_rows = weights[[asset_a, asset_b]].notna().all(axis=1)
        weights.loc[active_rows] = weights.loc[active_rows].fillna(0.0)
    return weights
