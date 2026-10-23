"""Portfolio-level backtest engine.

Strategies produce *target weights*: a DataFrame (dates x tickers) where row t
holds the portfolio the strategy wants to hold after the close of day t.
A row of all-NaN means "no rebalance today" — holdings simply drift with prices.

Timing convention (no look-ahead):
    weights decided at close t  ->  earn returns of day t+1.

Weights are fractions of NAV. Positive = long, negative = short; whatever is
not allocated sits in cash earning zero.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    gross_returns: pd.Series
    net_returns: pd.Series
    weights: pd.DataFrame      # holdings after rebalancing at each close
    turnover: pd.Series        # sum of |traded weight| per day
    costs: pd.Series
    delistings: pd.DataFrame = field(  # positions hit by a delisting
        default_factory=lambda: pd.DataFrame(columns=["date", "ticker", "weight"])
    )

    @property
    def equity(self) -> pd.Series:
        return (1 + self.net_returns).cumprod()

    @property
    def gross_equity(self) -> pd.Series:
        return (1 + self.gross_returns).cumprod()


DELISTING_RETURNS = {
    # Return applied on the day after a price series ends while still held.
    "last_price": 0.0,    # optimistic: exit at the last traded price
    "shumway": -0.30,     # Shumway (1997): avg performance-delisting return
    "total_loss": -1.0,   # pessimistic: position is worthless
}


def index_position(index: pd.Index, key: Hashable) -> int:
    """Integer position of a unique label (``Index.get_loc`` may also return
    a slice or mask for duplicate labels; that would be a bug here)."""
    pos = index.get_loc(key)
    if not isinstance(pos, int | np.integer):
        raise KeyError(f"label {key!r} is not unique in the index")
    return int(pos)


def ffill_within_life(prices: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill gaps *between* a ticker's first and last price only.

    A plain ``ffill`` would keep a dead stock trading at its last price forever,
    which silently hides delistings — a classic survivorship-bias leak.
    """
    filled = prices.ffill()
    return filled.where(prices.bfill().notna())


def delisting_days(prices: pd.DataFrame, grace: int = 5) -> pd.Series:
    """Map ticker -> first date *after* its last price, for series that end early.

    Series ending within ``grace`` rows of the end are treated as a data lag,
    not a delisting (a vendor being a few days behind is common).
    """
    idx = prices.index
    out: dict[Hashable, pd.Timestamp] = {}
    for ticker in prices.columns:
        last = prices[ticker].last_valid_index()
        if last is None:
            continue
        pos = index_position(idx, last)
        if pos < len(idx) - 1 - grace:
            out[ticker] = idx[pos + 1]
    return pd.Series(out, dtype="datetime64[ns]")


def run_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_rate: float = 0.001,
    delisting: str | float = "shumway",
) -> BacktestResult:
    """Simulate a portfolio that trades to ``target_weights`` at each close.

    Parameters
    ----------
    prices : DataFrame
        Adjusted close prices, dates x tickers. A ticker whose series ends
        before the last date is treated as delisted.
    target_weights : DataFrame
        Same shape/labels as ``prices`` (missing columns are treated as 0).
        All-NaN rows mean "hold, don't rebalance".
    cost_rate : float
        Proportional cost per unit of traded notional (0.001 = 10 bps).
    delisting : str or float
        Return credited to a held position when its stock delists: a key of
        ``DELISTING_RETURNS`` or a number (e.g. -0.5). The remaining value
        moves to cash and the stock can no longer be traded.
    """
    delist_ret = DELISTING_RETURNS[delisting] if isinstance(delisting, str) else float(delisting)

    target = target_weights.reindex(index=prices.index, columns=prices.columns)
    rebalance = target.notna().any(axis=1).to_numpy()
    if not rebalance.any():
        raise ValueError(
            "Strategy never produced a position (check parameters vs. universe size "
            "and warm-up windows vs. date range)."
        )
    target_arr = target.fillna(0.0).to_numpy()

    live = ffill_within_life(prices)
    ret_frame = live.pct_change(fill_method=None)
    dead_on = delisting_days(prices)
    col: dict[Hashable, int] = {c: i for i, c in enumerate(prices.columns)}
    delist_row = np.full(len(prices.columns), -1)
    for ticker, day in dead_on.items():
        delist_row[col[ticker]] = index_position(prices.index, day)
        ret_frame.loc[day, ticker] = delist_ret
    rets = ret_frame.fillna(0.0).to_numpy()
    # A stock cannot be bought before it lists or after it dies.
    tradable = live.notna().to_numpy()

    n_days, n_assets = rets.shape
    held = np.zeros((n_days, n_assets))
    gross = np.zeros(n_days)
    turnover = np.zeros(n_days)
    events = []

    w = np.zeros(n_assets)
    for t in range(n_days):
        if t > 0:
            port_ret = float(w @ rets[t])
            gross[t] = port_ret
            dying = delist_row == t
            # Judge "was it held" before the drift: a -100% delisting drifts a weight to zero.
            for i in np.flatnonzero(dying & (w != 0)):
                events.append((prices.index[t], prices.columns[int(i)], float(held[t - 1, i])))
            # Weights drift with prices; cash (1 - sum w) earns zero. If everything held was
            # wiped out (growth <= 0) there is nothing to rescale: 0/0 would leak NaN weights.
            growth = 1.0 + port_ret
            w = w * (1 + rets[t]) / growth if growth > 0 else np.zeros(n_assets)
            w[dying] = 0.0  # residual value converts to cash
        if rebalance[t]:
            desired = np.where(tradable[t], target_arr[t], 0.0)
            turnover[t] = np.abs(desired - w).sum()
            w = desired
        held[t] = w

    idx = prices.index
    gross_s = pd.Series(gross, index=idx, name="gross_return")
    turnover_s = pd.Series(turnover, index=idx, name="turnover")
    costs_s = turnover_s * cost_rate
    net_s = (gross_s - costs_s).rename("net_return")

    # Start the record on the first day the strategy actually holds something.
    sl = slice(int(np.argmax(rebalance)), None)
    return BacktestResult(
        gross_returns=gross_s.iloc[sl],
        net_returns=net_s.iloc[sl],
        weights=pd.DataFrame(held, index=idx, columns=prices.columns).iloc[sl],
        turnover=turnover_s.iloc[sl],
        costs=costs_s.iloc[sl],
        delistings=pd.DataFrame(events, columns=["date", "ticker", "weight"]),
    )
