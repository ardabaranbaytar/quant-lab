"""Turnover-aware tuning of Avellaneda-Lee, with a locked hold-out.

Validation: 2013–2018. Every variant is scored there (net Sharpe at 5 bps).
Hold-out:   2019–2024. Opened once, for the paper's default and the single
            variant chosen on validation — nothing else.

Usage:  python -m studies.al_tuning  -> reports/al_tuning.md
"""

from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantlab.data import clean_prices, load_prices
from quantlab.engine import run_backtest
from quantlab.metrics import performance_summary
from quantlab.strategies.residual_reversion import residual_reversion, s_scores
from quantlab.universe import (
    current_members,
    ever_members,
    load_sp500_gics,
    load_sp500_spells,
    membership_mask,
)
from studies.edge_search import SECTOR_ETF, spliced_hedges

START, END = "2010-01-01", "2024-12-31"
VALID = ("2013-01-01", "2018-12-31")
HOLDOUT = ("2019-01-01", "2024-12-31")
OUT = Path("reports")

GRID: dict[str, list[Any]] = {
    "s_open": [1.25, 1.75, 2.25],
    "s_smooth": [1, 5],
    "trade_every": [1, 5],
    "neutralize_with": [None, "SPY"],
}
PAPER: dict[str, Any] = {"s_open": 1.25, "s_smooth": 1, "trade_every": 1, "neutralize_with": None}


def stats(bt, lo: str, hi: str, spy: pd.Series) -> dict:
    net, gross = bt.net_returns.loc[lo:hi], bt.gross_returns.loc[lo:hi]
    s, g = performance_summary(net, turnover=bt.turnover.loc[lo:hi]), performance_summary(gross)
    both = pd.concat([net, spy.reindex(net.index)], axis=1).dropna()
    beta = np.cov(both.iloc[:, 0], both.iloc[:, 1])[0, 1] / both.iloc[:, 1].var()
    return {"sharpe_gross": g["sharpe"], "sharpe_net": s["sharpe"], "cagr_net": s["cagr"],
            "vol": s["volatility"], "max_dd": s["max_drawdown"], "beta_spy": beta,
            "turnover": s["annual_turnover"]}


def main() -> None:
    spells = load_sp500_spells()
    gics = load_sp500_gics()
    raw = load_prices(sorted(set(ever_members(spells, START, END)) | set(current_members(spells)) | {"SPY"}),
                      START, END)
    prices = clean_prices(raw)
    spy_px = prices.pop("SPY")
    spy = spy_px.pct_change()
    etf_px = clean_prices(load_prices(sorted(set(SECTOR_ETF.values())), START, END)).reindex(prices.index)

    sector = dict(zip(gics["ticker"], gics["sector"]))
    stocks = [t for t in prices.columns if t in sector and prices[t].notna().any()]
    hedges = spliced_hedges(etf_px[list(SECTOR_ETF.values())], spy_px)
    hedges["SPY"] = spy_px
    hedge_map = {t: SECTOR_ETF[sector[t]] for t in stocks}
    mask = membership_mask(spells, prices.index, stocks)
    px_all = pd.concat([prices[stocks], hedges], axis=1)

    rets = prices[stocks].pct_change(fill_method=None)
    hedge_rets = pd.DataFrame({s: hedges[hedge_map[s]].pct_change() for s in stocks}, index=prices.index)
    scores = s_scores(rets, hedge_rets)

    def backtest(params: dict, cost: float):
        w = residual_reversion(prices[stocks], hedge_map, hedges, universe=mask, scores=scores, **params)
        return run_backtest(px_all, w, cost)

    rows = []
    keys = list(GRID)
    for values in product(*GRID.values()):
        params = dict(zip(keys, values))
        bt = backtest(params, 0.0005)
        rows.append({**params, **stats(bt, *VALID, spy)})
        print({k: v for k, v in rows[-1].items() if k in keys or k in ("sharpe_net", "turnover")})
    grid = pd.DataFrame(rows).sort_values("sharpe_net", ascending=False)
    best = grid.iloc[0]
    chosen: dict[str, Any] = {
        "s_open": float(best["s_open"]),
        "s_smooth": int(best["s_smooth"]),
        "trade_every": int(best["trade_every"]),
        "neutralize_with": best["neutralize_with"] if isinstance(best["neutralize_with"], str) else None,
    }
    print("chosen on validation:", chosen)

    final_rows: list[dict[str, Any]] = []
    for label, params in [("paper default", PAPER), ("chosen on 2013–2018", chosen)]:
        for cost in (0.0005, 0.001):
            bt = backtest(params, cost)
            for period, (lo, hi) in [("validation 2013–2018", VALID), ("HOLD-OUT 2019–2024", HOLDOUT)]:
                final_rows.append({"variant": label, "cost_bps": cost * 1e4, "period": period, **stats(bt, lo, hi, spy)})
    final = pd.DataFrame(final_rows)
    pd.set_option("display.width", 250)
    print(final.round(3).to_string(index=False))

    def fmt(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for c in ["cagr_net", "vol", "max_dd"]:
            df[c] = df[c].map(lambda v: f"{v:.1%}")
        for c in ["sharpe_gross", "sharpe_net", "beta_spy"]:
            df[c] = df[c].map(lambda v: f"{v:.2f}")
        df["turnover"] = df["turnover"].map(lambda v: f"{v:.0f}×")
        return df

    g = grid.copy()
    g["neutralize_with"] = g["neutralize_with"].fillna("—")
    OUT.mkdir(exist_ok=True)
    (OUT / "al_tuning.md").write_text(
        "# Avellaneda-Lee: turnover-aware tuning with a locked hold-out\n\n"
        f"All {len(grid)} variants scored on **2013–2018 only** (net Sharpe, 5 bps per side). "
        "The best one and the paper's default were then run once on the 2019–2024 hold-out.\n\n"
        "## Hold-out result\n\n" + fmt(final).to_markdown(index=False)
        + f"\n\nChosen parameters: `{chosen}`\n\n"
        "## Full validation grid (2013–2018, 5 bps)\n\n" + fmt(g).to_markdown(index=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUT / 'al_tuning.md'}")


if __name__ == "__main__":
    main()
