"""Multi-pair stat-arb on the point-in-time S&P 500, with and without the
break monitor.

Usage:  python -m studies.pair_portfolio  -> reports/pair_portfolio.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantlab.data import clean_prices, load_prices
from quantlab.engine import run_backtest
from quantlab.metrics import performance_summary
from quantlab.risk import BreakMonitor
from quantlab.strategies.pair_portfolio import run_pair_portfolio
from quantlab.universe import (
    current_members,
    ever_members,
    load_sp500_gics,
    load_sp500_spells,
    membership_mask,
)

START, END = "2010-01-01", "2024-12-31"
COST = 0.001
OUT = Path("reports")
PARAMS: dict[str, Any] = {"formation_days": 756, "trading_days": 63, "top_k": 20, "entry_z": 2.0, "exit_z": 0.0}


def main() -> None:
    spells = load_sp500_spells()
    gics = load_sp500_gics()
    groups = dict(zip(gics["ticker"], gics["sub_industry"]))
    companies = dict(zip(gics["ticker"], gics["company"]))

    # Same ticker set as the survivorship study -> reuses its price cache.
    raw = load_prices(sorted(set(ever_members(spells, START, END)) | set(current_members(spells)) | {"SPY"}),
                      START, END)
    prices = clean_prices(raw)
    spy = prices.pop("SPY").pct_change()
    tradable = [t for t in prices.columns if t in groups and prices[t].notna().any()]
    prices = prices[tradable]
    mask = membership_mask(spells, prices.index, tradable)
    print(f"universe: {len(tradable)} classified tickers, {len({groups[t] for t in tradable})} sub-industries")

    real_path = OUT / "real_thresholds.json"
    variants: dict[str, dict[str, Any]] = {"no risk layer": {}, "z-stop 4": {"stop_z": 4.0},
                "monitor (synthetic calibration)": {"break_monitor": BreakMonitor()}}
    if real_path.exists():
        th = json.loads(real_path.read_text())
        variants["monitor (real calibration, 2 votes)"] = {"break_monitor": BreakMonitor(thresholds=th, break_votes=2)}

    cache: dict = {}
    rows, yearly, details = [], {}, {}
    for name, kw in variants.items():
        res = run_pair_portfolio(prices, groups, universe=mask, selection_cache=cache,
                                 companies=companies, **PARAMS, **kw)
        bt = run_backtest(prices, res.weights, COST)
        r = bt.net_returns
        s = performance_summary(r, turnover=bt.turnover)
        aligned = pd.concat([r, spy.reindex(r.index)], axis=1).dropna()
        beta = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1] / aligned.iloc[:, 1].var()
        gross = bt.weights.abs().sum(axis=1)
        gross_s = performance_summary(bt.gross_returns)
        rows.append({
            "variant": name, "sharpe_before_costs": gross_s["sharpe"], "total_return": s["total_return"], "cagr": s["cagr"], "volatility": s["volatility"],
            "sharpe": s["sharpe"], "max_drawdown": s["max_drawdown"], "beta_to_spy": beta,
            "corr_to_spy": aligned.corr().iloc[0, 1], "avg_gross_exposure": gross.mean(),
            "annual_turnover": s["annual_turnover"], "risk_exits": len(res.risk_exits),
        })
        yearly[name] = (1 + r).groupby(pd.DatetimeIndex(r.index).year).prod() - 1
        details[name] = res
        print(f"{name:38s} total {s['total_return']:+7.1%} sharpe {s['sharpe']:5.2f} maxDD {s['max_drawdown']:6.1%} "
              f"beta {beta:+.2f} exits {len(res.risk_exits)}")

    table = pd.DataFrame(rows)
    first = next(iter(details.values()))
    r0 = run_backtest(prices, first.weights, COST).net_returns
    spy_r = spy.reindex(r0.index).fillna(0)
    s = performance_summary(spy_r)
    yearly["SPY"] = (1 + spy_r).groupby(pd.DatetimeIndex(spy_r.index).year).prod() - 1
    table = pd.concat([table, pd.DataFrame([{"variant": "SPY buy & hold", "total_return": s["total_return"],
                                             "cagr": s["cagr"], "volatility": s["volatility"], "sharpe": s["sharpe"],
                                             "max_drawdown": s["max_drawdown"], "beta_to_spy": 1.0,
                                             "corr_to_spy": 1.0}])], ignore_index=True)
    yearly_df = pd.DataFrame(yearly)
    yearly_df = yearly_df[yearly_df.index >= pd.Timestamp(r0.index[int(r0.ne(0).argmax())]).year]

    sel = first.selections
    n_periods = sel["period_start"].nunique()
    by_group = sel["group"].value_counts().head(10)

    fmt = table.copy()
    for c in ["total_return", "cagr", "volatility", "max_drawdown", "avg_gross_exposure"]:
        fmt[c] = fmt[c].map(lambda v: "—" if pd.isna(v) else f"{v:.1%}")
    for c in ["sharpe_before_costs", "sharpe", "beta_to_spy", "corr_to_spy", "annual_turnover"]:
        fmt[c] = fmt[c].map(lambda v: "—" if pd.isna(v) else f"{v:.2f}")
    fmt["risk_exits"] = fmt["risk_exits"].map(lambda v: "—" if pd.isna(v) else f"{int(v)}")

    OUT.mkdir(exist_ok=True)
    (OUT / "pair_portfolio.md").write_text(
        f"# Multi-pair stat-arb on the point-in-time S&P 500 ({START[:4]}–{END[:4]})\n\n"
        f"Quarterly re-selection: same GICS sub-industry, Engle-Granger p < 0.05 on {PARAMS['formation_days']} "
        f"days of log prices, half-life 5–60 days, top {PARAMS['top_k']} pairs (≤ 2 per stock), each 1/"
        f"{PARAMS['top_k']} of capital; entry |z| > 2, exit z = 0; {COST * 1e4:.0f} bps costs. "
        f"Universe: {len(tradable)} tickers classified by today's GICS (removed companies can't be grouped — "
        "residual survivorship bias).\n\n"
        + fmt.to_markdown(index=False)
        + "\n\n## Calendar-year returns\n\n"
        + yearly_df.map(lambda v: "—" if pd.isna(v) else f"{v:+.1%}").to_markdown()
        + f"\n\n## Selection statistics\n\n- Periods: {n_periods}; pairs selected per period: "
        f"mean {len(sel) / max(n_periods, 1):.1f}\n- Most frequent sub-industries:\n\n"
        + by_group.to_frame("pair-periods").to_markdown()
        + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUT / 'pair_portfolio.md'}")


if __name__ == "__main__":
    main()
