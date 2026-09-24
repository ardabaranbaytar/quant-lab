"""Survivorship-bias study: the same momentum strategy on three universes.

A. today's S&P 500 constituents        (what most tutorials do — biased)
B. point-in-time S&P 500 membership    (only stocks in the index on each date)
   under three delisting assumptions

Usage:  python -m studies.survivorship
Writes: reports/survivorship.md and reports/survivorship.csv
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from quantlab.data import clean_prices, load_prices
from quantlab.engine import run_backtest
from quantlab.metrics import performance_summary
from quantlab.strategies import cross_sectional_momentum
from quantlab.strategies.cross_sectional import month_end_dates
from quantlab.universe import (
    coverage_report,
    current_members,
    ever_members,
    load_sp500_spells,
    membership_mask,
)

START, END = "2010-01-01", "2024-12-31"
PARAMS: dict[str, Any] = {"lookback": 60, "top_n": 20}
COST = 0.001
OUT = Path("reports")


def summarise(name: str, result, universe_size: int) -> dict:
    s = performance_summary(result.net_returns, turnover=result.turnover)
    return {
        "universe": name,
        "tickers": universe_size,
        "total_return": s["total_return"],
        "cagr": s["cagr"],
        "sharpe": s["sharpe"],
        "max_drawdown": s["max_drawdown"],
        "delisting_events": len(result.delistings),
    }


def main() -> None:
    spells = load_sp500_spells()
    today = current_members(spells)
    ever = ever_members(spells, START, END)
    print(f"today's members: {len(today)} | members at any point {START[:4]}-{END[:4]}: {len(ever)}")

    raw = load_prices(sorted(set(ever) | set(today) | {"SPY"}), START, END)
    prices = clean_prices(raw)
    spy = prices.pop("SPY") if "SPY" in prices else None
    no_data = sorted(set(ever) - set(prices.columns[prices.notna().any()]))
    print(f"members with no price data at all: {len(no_data)} ({len(no_data) / len(ever):.0%})")

    rows = []

    # A. Today's constituents, as if they had always been the index.
    a_cols = [t for t in today if t in prices.columns]
    a_px = prices[a_cols]
    res_a = run_backtest(a_px, cross_sectional_momentum(a_px, **PARAMS), COST)
    rows.append(summarise("A. Today's S&P 500 (biased)", res_a, len(a_cols)))

    # A2. Every stock that was ever a member, but with no date filter: it can
    # be bought years before it joined — i.e. because we know it will join.
    b_cols = [t for t in ever if t in prices.columns and prices[t].notna().any()]
    b_px = prices[b_cols]
    res_a2 = run_backtest(b_px, cross_sectional_momentum(b_px, **PARAMS), COST)
    rows.append(summarise("A2. Ever-members, no date filter", res_a2, len(b_cols)))

    # B. Point-in-time membership.
    mask = membership_mask(spells, b_px.index, b_cols)
    b_weights = cross_sectional_momentum(b_px, **PARAMS, universe=mask)
    for policy in ["last_price", "shumway", "total_loss"]:
        res_b = run_backtest(b_px, b_weights, COST, delisting=policy)
        rows.append(summarise(f"B. Point-in-time, delisting={policy}", res_b, len(b_cols)))

    if spy is not None:
        spy_ret = spy.pct_change().loc[res_a.net_returns.index].fillna(0.0)
        s = performance_summary(spy_ret)
        rows.append({"universe": "SPY buy & hold", "tickers": 1, **{k: s[k] for k in
                     ["total_return", "cagr", "sharpe", "max_drawdown"]}, "delisting_events": 0})

    table = pd.DataFrame(rows)

    # Where A's edge comes from: months each stock was held before it joined.
    a_w = cross_sectional_momentum(a_px, **PARAMS).dropna(how="all")
    joined = spells[spells["end_date"].isna()].groupby("ticker")["start_date"].max()
    pre = pd.DataFrame({
        "months_held": (a_w > 0).sum(),
        "joined_index": joined.reindex(a_w.columns).dt.date,
    })
    a_member = membership_mask(spells, a_w.index, a_w.columns)
    pre["held_while_not_member"] = ((a_w > 0) & ~a_member).sum()
    pre = pre[pre.held_while_not_member > 0].sort_values("held_while_not_member", ascending=False).head(15)
    full_mask = membership_mask(spells, prices.index, ever)
    cov = coverage_report(full_mask, prices, month_end_dates(prices.index))
    print(table.round(3).to_string(index=False))
    print(f"\nPIT coverage at rebalances: mean {cov.coverage.mean():.1%}, min {cov.coverage.min():.1%}")

    OUT.mkdir(exist_ok=True)
    table.to_csv(OUT / "survivorship.csv", index=False)
    fmt = table.copy()
    for c in ["total_return", "cagr", "max_drawdown"]:
        fmt[c] = fmt[c].map(lambda v: f"{v:.1%}")
    fmt["sharpe"] = fmt["sharpe"].map(lambda v: f"{v:.2f}")
    by_year = cov.groupby(pd.DatetimeIndex(cov.index).year)["coverage"].mean()
    (OUT / "survivorship.md").write_text(
        f"# Survivorship-bias study ({START[:4]}–{END[:4]})\n\n"
        f"Strategy: monthly cross-sectional momentum, lookback {PARAMS['lookback']}d, "
        f"top {PARAMS['top_n']}, costs {COST * 1e4:.0f} bps.\n\n"
        + fmt.to_markdown(index=False)
        + "\n\n## Where the biased edge comes from\n\n"
        "Stocks the biased universe (A) held *before* they joined the S&P 500 — "
        "bought because we already know they will become large caps:\n\n"
        + pre.to_markdown()
        + "\n\n## Data coverage of point-in-time members\n\n"
        f"- Members at any point: {len(ever)}; with no Yahoo prices: {len(no_data)} "
        f"({len(no_data) / len(ever):.0%})\n"
        f"- Coverage at rebalance dates: mean {cov.coverage.mean():.1%}, min {cov.coverage.min():.1%}\n\n"
        + by_year.map(lambda v: f"{v:.1%}").rename("coverage").to_frame().to_markdown()
        + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUT / 'survivorship.md'}")


if __name__ == "__main__":
    main()
