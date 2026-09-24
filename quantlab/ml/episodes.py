"""Turn the pair portfolio's entry signals into a supervised dataset.

An *episode* starts when a selected pair's |z| exceeds ``entry_z`` while
flat (the same rule the portfolio uses). For each episode we record:

- **features**, using only information available at that day's close;
- **the outcome** of entering there under the portfolio's own exit rules
  (exit when z crosses ``exit_z``, or at the end of the trading period),
  net of round-trip costs. ``label = pnl > 0``.

Every episode is simulated, including ones that start while the baseline
portfolio would already be in a trade — so the dataset matches what a
filtered portfolio can encounter.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

from quantlab.engine import index_position
from quantlab.risk.detectors import DETECTORS, compute_detectors
from quantlab.strategies.pair_portfolio import pairs_from_frame

FEATURES = [
    # the signal itself
    "abs_z", "z_jump_5d", "z_max_20d", "days_into_period", "days_left",
    # formation-period quality of the pair
    "pvalue", "half_life", "abs_beta", "formation_corr", "spread_std",
    # how the divergence happened: one leg or both, sudden or gradual
    "move_share_a", "ret_5d_cheap_leg", "ret_5d_rich_leg", "vol_ratio_a", "vol_ratio_b",
    # market regime
    "mkt_ret_20d", "mkt_vol_20d",
    # break detectors (risk layer) as features
    *DETECTORS, "roll_half_life",
]


def _simulate(z: np.ndarray, pair_ret: np.ndarray, k0: int, exit_z: float) -> tuple[int, float]:
    """Hold from close k0; return (exit index, cumulative pair return)."""
    pos = -1.0 if z[k0] > 0 else 1.0
    pnl = 0.0
    k = k0
    for k in range(k0 + 1, len(z)):
        pnl += pos * pair_ret[k] if not np.isnan(pair_ret[k]) else 0.0
        if np.isnan(z[k]):
            break
        if (pos > 0 and z[k] >= -exit_z) or (pos < 0 and z[k] <= exit_z):
            break
    return k, pnl


def build_episodes(
    prices: pd.DataFrame,
    selections: pd.DataFrame,
    market_returns: pd.Series,
    trading_days: int = 63,
    entry_z: float = 2.0,
    exit_z: float = 0.0,
    cost_rate: float = 0.001,
) -> pd.DataFrame:
    idx = prices.index
    log_px = cast(pd.DataFrame, np.log(prices))
    log_arr = {c: log_px[c].to_numpy() for c in prices.columns}
    rets = log_px.diff()
    vol_ratio = rets.rolling(20).std() / rets.rolling(252).std().shift(21)
    vol_ratio_arr = {c: vol_ratio[c].to_numpy() for c in prices.columns}
    mkt = market_returns.reindex(idx)
    mkt_ret20 = (1 + mkt).rolling(20).apply(np.prod, raw=True) - 1
    mkt_vol20 = mkt.rolling(20).std() * np.sqrt(252)
    mkt_ret20_arr, mkt_vol20_arr = mkt_ret20.to_numpy(), mkt_vol20.to_numpy()

    det_cache: dict[tuple[str, str], pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    starts = [pd.Timestamp(d) for d in selections["period_start"]]
    for period_start, p in zip(starts, pairs_from_frame(selections)):
        start = index_position(idx, period_start)
        end = min(start + trading_days, len(idx))
        lo = max(start - 25, 0)
        la = log_arr[p.a][lo:end]
        lb = log_arr[p.b][lo:end]
        z_all = (la - p.beta * lb - p.alpha - p.mean) / p.std
        gross = 1 + abs(p.beta)
        pair_ret = np.r_[np.nan, np.diff(la) - p.beta * np.diff(lb)] / gross
        off = start - lo  # position of period start inside the arrays

        key = (p.a, p.b)
        if key not in det_cache:
            det_cache[key] = compute_detectors(prices[p.a], prices[p.b])
        det = det_cache[key]
        form = rets[[p.a, p.b]].iloc[max(start - 755, 1) : start + 1]
        form_corr = form[p.a].corr(form[p.b])

        armed = True
        z_period = z_all[off:]
        for k0 in range(len(z_period)):
            zk = z_period[k0]
            if np.isnan(zk):
                continue
            if abs(zk) < entry_z:
                armed = True
                continue
            if not armed:
                continue
            armed = False
            t = start + k0
            date = idx[t]
            k_exit, pnl = _simulate(z_period, pair_ret[off:], k0, exit_z)
            pnl -= 2 * cost_rate  # enter + exit, gross exposure 1

            cheap, rich = (p.a, p.b) if zk < 0 else (p.b, p.a)
            r5 = {c: float(log_arr[c][t] - log_arr[c][max(t - 5, 0)]) for c in (p.a, p.b)}
            move_a = abs(r5[p.a]) / (abs(r5[p.a]) + abs(r5[p.b]) + 1e-12)
            zi = off + k0
            row = {
                "a": p.a, "b": p.b, "group": p.group, "entry_date": date,
                "exit_date": idx[start + k_exit], "holding_days": k_exit - k0,
                "side": "long_a" if zk < 0 else "short_a",
                "pnl": pnl, "label": int(pnl > 0),
                "abs_z": abs(zk),
                "z_jump_5d": abs(zk) - abs(z_all[zi - 5]) if zi >= 5 else np.nan,
                "z_max_20d": np.nanmax(np.abs(z_all[max(zi - 20, 0) : zi + 1])),
                "days_into_period": k0, "days_left": (end - start) - k0,
                "pvalue": p.pvalue, "half_life": p.half_life, "abs_beta": abs(p.beta),
                "formation_corr": form_corr, "spread_std": p.std,
                "move_share_a": move_a,
                "ret_5d_cheap_leg": r5[cheap], "ret_5d_rich_leg": r5[rich],
                "vol_ratio_a": vol_ratio_arr[p.a][t],
                "vol_ratio_b": vol_ratio_arr[p.b][t],
                "mkt_ret_20d": mkt_ret20_arr[t], "mkt_vol_20d": mkt_vol20_arr[t],
                "roll_half_life": det["half_life"].iat[t],
            }
            for d in DETECTORS:
                row[d] = det[d].iat[t]
            rows.append(row)
    return pd.DataFrame(rows)
