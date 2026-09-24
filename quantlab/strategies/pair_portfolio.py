"""Multi-pair statistical arbitrage with periodic pair re-selection.

Every ``trading_days`` (a quarter by default):

1. **Formation** — among stocks eligible on that date (point-in-time members
   with a full ``formation_days`` price history), test every same-group pair
   for cointegration (Engle-Granger on log prices). Keep pairs with
   p < ``max_pvalue`` and a mean-reversion half-life inside
   ``half_life_range``; take the best ``top_k``, each stock in at most
   ``max_pairs_per_stock`` pairs.
2. **Trading** — for the next period, trade each selected pair on the z-score
   of its spread ``log A - beta log B`` (beta, mean and std frozen from the
   formation window). Each pair gets ``1/top_k`` of capital.
3. **Risk** — an optional :class:`~quantlab.risk.BreakMonitor` closes a pair
   the moment it is flagged BROKEN and blocks entries on WARNING.

Pairs that stop cointegrating simply drop out at the next re-selection —
the main defence against *slow* breaks (a company eroding over many months).
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from functools import partial
from itertools import combinations
from typing import Any, cast

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

from quantlab.risk.monitor import BROKEN, NORMAL, WARNING, BreakMonitor

EntryFilter = Callable[[str, str, pd.Timestamp], bool]


@dataclass(frozen=True)
class SelectedPair:
    """A pair chosen in a formation window, with its frozen spread model."""

    a: str
    b: str
    group: str
    pvalue: float
    half_life: float
    beta: float
    alpha: float
    mean: float
    std: float


PAIR_COLUMNS = [f.name for f in fields(SelectedPair)]


def pairs_from_frame(frame: pd.DataFrame) -> list[SelectedPair]:
    rows: list[dict[str, Any]] = cast(list[dict[str, Any]], frame[PAIR_COLUMNS].to_dict("records"))
    return [
        SelectedPair(a=str(r["a"]), b=str(r["b"]), group=str(r["group"]),
                     **{k: float(r[k]) for k in PAIR_COLUMNS[3:]})
        for r in rows
    ]


@dataclass
class PairPortfolioResult:
    weights: pd.DataFrame
    selections: pd.DataFrame = field(default_factory=pd.DataFrame)  # one row per pair per period
    risk_exits: pd.DataFrame = field(default_factory=pd.DataFrame)  # monitor-forced exits


def pair_zscore(p: SelectedPair, price_a: float, price_b: float) -> float:
    """z-score of the spread ``log A - beta log B - alpha`` under the frozen model."""
    spread = np.log(price_a) - p.beta * np.log(price_b) - p.alpha
    return float((spread - p.mean) / p.std)


def leg_weights(pos: int, beta: float, top_k: int) -> tuple[float, float]:
    """NAV weights of legs A and B for one open pair (1 : beta, 1/top_k of capital)."""
    gross = 1 + abs(beta)
    return pos / gross / top_k, -pos * beta / gross / top_k


def next_position(
    pos: int,
    armed: bool,
    z: float,
    state: int,
    entry_z: float,
    exit_z: float,
    stop_z: float | None,
    allow_entry: Callable[[], bool] | None = None,
) -> tuple[int, bool, str | None]:
    """One day of the per-pair state machine -> ``(pos, armed, event)``.

    Shared by the backtest and the paper-trading bot so both make identical
    decisions. ``armed`` is False after a stop/veto until |z| re-enters the
    entry band. Events: entry, exit, stop, risk_exit, delisted, vetoed.
    """
    if np.isnan(z):                    # a leg stopped trading (e.g. delisted)
        return 0, armed, ("delisted" if pos else None)
    if abs(z) < entry_z:
        armed = True
    if pos != 0 and state == BROKEN:
        return 0, armed, "risk_exit"
    if pos == 0:
        if armed and state not in (BROKEN, WARNING) and abs(z) > entry_z:
            if allow_entry is None or allow_entry():
                return (-1 if z > 0 else 1), armed, "entry"
            return 0, False, "vetoed"
        return 0, armed, None
    if stop_z is not None and abs(z) > stop_z:
        return 0, False, "stop"
    if (pos == 1 and z >= -exit_z) or (pos == -1 and z <= exit_z):
        return 0, armed, "exit"
    return pos, armed, None


def _half_life(resid: np.ndarray) -> float:
    x = resid[:-1] - resid[:-1].mean()
    dy = np.diff(resid)
    slope = float((x * (dy - dy.mean())).sum() / (x**2).sum())
    return -np.log(2) / slope if -1 < slope < 0 else np.inf


def select_pairs(
    log_px: pd.DataFrame,
    groups: dict[str, str],
    max_pvalue: float = 0.05,
    half_life_range: tuple[float, float] = (5, 60),
    top_k: int = 20,
    max_pairs_per_stock: int = 2,
    max_return_corr: float = 0.97,
    companies: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Rank same-group pairs in a formation window of log prices.

    Pairs whose daily returns correlate above ``max_return_corr`` are skipped:
    they are share classes of one company (GOOG/GOOGL, FOX/FOXA), whose
    "spread" is a technicality, not a relative-value bet. ``companies``
    (ticker -> issuer name) excludes share classes explicitly.
    """
    rets = log_px.diff().iloc[1:]
    by_group: dict[str, list[str]] = {}
    for t in log_px.columns:
        if t in groups:
            by_group.setdefault(groups[t], []).append(t)

    candidates: list[SelectedPair] = []
    for group, members in by_group.items():
        for a, b in combinations(sorted(members), 2):
            if companies and companies.get(a) is not None and companies.get(a) == companies.get(b):
                continue
            if rets[a].corr(rets[b]) > max_return_corr:
                continue
            ya, yb = log_px[a].to_numpy(), log_px[b].to_numpy()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _, pvalue, _ = coint(ya, yb, maxlag=1, autolag=None)
            if pvalue >= max_pvalue:
                continue
            beta, alpha = np.polyfit(yb, ya, 1)
            resid = ya - beta * yb - alpha
            hl = _half_life(resid)
            if not half_life_range[0] <= hl <= half_life_range[1]:
                continue
            candidates.append(SelectedPair(
                a=a, b=b, group=group, pvalue=float(pvalue), half_life=hl, beta=float(beta),
                alpha=float(alpha), mean=float(resid.mean()), std=float(resid.std()),
            ))

    used: dict[str, int] = {}
    chosen: list[SelectedPair] = []
    for pair in sorted(candidates, key=lambda p: (p.pvalue, p.half_life)):
        if used.get(pair.a, 0) >= max_pairs_per_stock or used.get(pair.b, 0) >= max_pairs_per_stock:
            continue
        chosen.append(pair)
        used[pair.a] = used.get(pair.a, 0) + 1
        used[pair.b] = used.get(pair.b, 0) + 1
        if len(chosen) == top_k:
            break
    return pd.DataFrame([asdict(p) for p in chosen], columns=PAIR_COLUMNS)


def run_pair_portfolio(
    prices: pd.DataFrame,
    groups: dict[str, str],
    universe: pd.DataFrame | None = None,
    formation_days: int = 756,
    trading_days: int = 63,
    top_k: int = 20,
    max_pvalue: float = 0.05,
    half_life_range: tuple[float, float] = (5, 60),
    max_pairs_per_stock: int = 2,
    entry_z: float = 2.0,
    exit_z: float = 0.0,
    stop_z: float | None = None,
    break_monitor: BreakMonitor | None = None,
    selection_cache: dict[tuple, pd.DataFrame] | None = None,
    companies: dict[str, str] | None = None,
    entry_filter: EntryFilter | None = None,
) -> PairPortfolioResult:
    """See module docstring. ``selection_cache`` (a dict) memoises formation
    results per period so several risk variants can share one pair selection.
    ``entry_filter(a, b, date) -> bool`` can veto an entry signal (e.g. an ML
    model); a vetoed signal is skipped until |z| falls back inside ``entry_z``."""
    idx, cols = prices.index, list(prices.columns)
    col = {c: i for i, c in enumerate(cols)}
    log_px = cast(pd.DataFrame, np.log(prices))
    target = np.full((len(idx), len(cols)), np.nan)
    if universe is not None:
        universe = universe.reindex(index=idx, columns=cols, fill_value=False)

    state_cache: dict[tuple[str, str], np.ndarray] = {}

    def risk_state(a: str, b: str) -> np.ndarray:
        if break_monitor is None:
            return np.full(len(idx), NORMAL)
        if (a, b) not in state_cache:
            px = prices[[a, b]]
            state_cache[(a, b)] = break_monitor.evaluate_pair(px[a], px[b])["state"].reindex(idx).fillna(0).to_numpy()
        return state_cache[(a, b)]

    selections: list[dict[str, Any]] = []
    exits: list[dict[str, Any]] = []
    for start in range(formation_days, len(idx), trading_days):
        end = min(start + trading_days, len(idx))
        window = log_px.iloc[start - formation_days + 1 : start + 1]
        eligible = list(window.columns[window.notna().all()])
        if universe is not None:
            eligible = [t for t in eligible if universe.iat[start, col[t]]]
        key = (start, formation_days, top_k, max_pvalue, half_life_range, max_pairs_per_stock)
        if selection_cache is not None and key in selection_cache:
            pairs = selection_cache[key]
        else:
            pairs = select_pairs(window[eligible], groups, max_pvalue, half_life_range, top_k,
                                 max_pairs_per_stock, companies=companies)
            if selection_cache is not None:
                selection_cache[key] = pairs

        book = np.zeros((end - start, len(cols)))
        for p in pairs_from_frame(pairs):
            ia, ib = col[p.a], col[p.b]
            spread = log_px[p.a].iloc[start:end].to_numpy() - p.beta * log_px[p.b].iloc[start:end].to_numpy() - p.alpha
            z = (spread - p.mean) / p.std
            state = risk_state(p.a, p.b)[start:end]
            pos, armed = 0, True
            for k in range(end - start):
                allow = None if entry_filter is None else partial(entry_filter, p.a, p.b, idx[start + k])
                pos, armed, event = next_position(pos, armed, z[k], int(state[k]),
                                                  entry_z, exit_z, stop_z, allow)
                if event == "risk_exit":
                    exits.append({"date": idx[start + k], "pair": f"{p.a}/{p.b}", "z": z[k]})
                if pos:
                    wa, wb = leg_weights(pos, p.beta, top_k)
                    book[k, ia] += wa
                    book[k, ib] += wb
            selections.append({"period_start": idx[start], **asdict(p)})

        # Only emit a target when the book changes (else holdings drift).
        prev: np.ndarray | None = None
        for k in range(end - start):
            if prev is None or not np.allclose(book[k], prev):
                target[start + k] = book[k]
                prev = book[k]

    weights = pd.DataFrame(target, index=idx, columns=cols)
    return PairPortfolioResult(weights, pd.DataFrame(selections), pd.DataFrame(exits))


def pair_portfolio(prices: pd.DataFrame, groups: dict[str, str] | None = None, **kwargs) -> pd.DataFrame:
    """Strategy-interface wrapper: prices -> target weights."""
    if groups is None:  # one group: every pair in the universe is a candidate
        groups = {c: "all" for c in prices.columns}
    return run_pair_portfolio(prices, groups, **kwargs).weights
