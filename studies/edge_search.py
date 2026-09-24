"""Edge search with pre-registered parameters.

A. Avellaneda-Lee residual reversion on the point-in-time S&P 500, hedged with
   SPDR sector ETFs — parameters exactly as published in 2010, so every year
   here is out-of-sample for the method.
B. Pairs trading on liquid ETFs (sectors, industries, countries, commodities,
   bonds) — baskets don't go bankrupt, so relationships should be sturdier.
C. The stock-pair portfolio from studies.pair_portfolio, for reference.

Results are reported for the full period and for two halves (2013–2018,
2019–2024) to show whether any edge is stable.

Usage:  python -m studies.edge_search  -> reports/edge_search.md
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from quantlab.data import clean_prices, load_prices
from quantlab.engine import run_backtest
from quantlab.metrics import performance_summary
from quantlab.strategies.pair_portfolio import run_pair_portfolio
from quantlab.strategies.residual_reversion import residual_reversion
from quantlab.universe import (
    current_members,
    ever_members,
    load_sp500_gics,
    load_sp500_spells,
    membership_mask,
)

START, END = "2010-01-01", "2024-12-31"
EVAL_START = "2013-01-01"
HALVES = [("2013–2018", "2013-01-01", "2018-12-31"), ("2019–2024", "2019-01-01", "2024-12-31")]
OUT = Path("reports")

SECTOR_ETF = {
    "Information Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Health Care": "XLV",
    "Industrials": "XLI", "Consumer Staples": "XLP", "Consumer Discretionary": "XLY",
    "Utilities": "XLU", "Materials": "XLB", "Real Estate": "XLRE", "Communication Services": "XLC",
}

ETF_GROUPS = {
    "us_sector": ["XLK", "XLF", "XLE", "XLV", "XLI", "XLP", "XLY", "XLU", "XLB"],
    "us_industry": ["XOP", "OIH", "XME", "KRE", "KBE", "SMH", "IBB", "XBI", "ITB", "XHB", "IYR", "VNQ", "XRT"],
    "us_broad": ["SPY", "QQQ", "DIA", "IWM", "MDY", "IWD", "IWF"],
    "country": ["EFA", "EEM", "EWJ", "EWG", "EWU", "EWC", "EWA", "EWZ", "EWH", "EWT", "EWY", "EWS", "EWW", "FXI"],
    "commodity": ["GLD", "SLV", "GDX", "GDXJ", "USO", "DBA", "DBC"],
    "bond": ["TLT", "IEF", "SHY", "LQD", "HYG", "TIP", "AGG", "MUB"],
}


def spliced_hedges(etfs: pd.DataFrame, spy: pd.Series) -> pd.DataFrame:
    """Sector ETF prices, with SPY returns before an ETF existed (XLRE 2015, XLC 2018)."""
    out = {}
    for c in etfs.columns:
        r = etfs[c].pct_change(fill_method=None)
        r = r.where(etfs[c].notna() & etfs[c].shift().notna(), spy.pct_change())
        out[c] = 100 * (1 + r.fillna(0)).cumprod()
    return pd.DataFrame(out)


def summarise(name: str, net: pd.Series, gross: pd.Series, weights: pd.DataFrame, spy: pd.Series) -> list[dict]:
    rows = []
    for label, lo, hi in [("2013–2024", EVAL_START, END), *HALVES]:
        r, g = net.loc[lo:hi], gross.loc[lo:hi]
        s, sg = performance_summary(r), performance_summary(g)
        both = pd.concat([r, spy.reindex(r.index)], axis=1).dropna()
        beta = np.cov(both.iloc[:, 0], both.iloc[:, 1])[0, 1] / both.iloc[:, 1].var()
        rows.append({"strategy": name, "period": label, "sharpe_gross": sg["sharpe"], "sharpe_net": s["sharpe"],
                     "cagr_net": s["cagr"], "vol": s["volatility"], "max_dd": s["max_drawdown"],
                     "beta_spy": beta, "gross_exposure": weights.loc[lo:hi].abs().sum(axis=1).mean()})
    return rows


def main() -> None:
    spells = load_sp500_spells()
    gics = load_sp500_gics()
    raw = load_prices(sorted(set(ever_members(spells, START, END)) | set(current_members(spells)) | {"SPY"}),
                      START, END)
    prices = clean_prices(raw)
    spy_px = prices.pop("SPY")
    spy = spy_px.pct_change()

    etf_list = sorted({t for g in ETF_GROUPS.values() for t in g} | set(SECTOR_ETF.values()))
    etf_px = clean_prices(load_prices(etf_list, START, END)).reindex(prices.index)
    rows = []

    # --- A. Avellaneda-Lee residual reversion -------------------------------
    sector = dict(zip(gics["ticker"], gics["sector"]))
    stocks = [t for t in prices.columns if t in sector and prices[t].notna().any()]
    hedges = spliced_hedges(etf_px[list(SECTOR_ETF.values())], spy_px)
    hedge_map = {t: SECTOR_ETF[sector[t]] for t in stocks}
    mask = membership_mask(spells, prices.index, stocks)
    w_al = residual_reversion(prices[stocks], hedge_map, hedges, universe=mask, position_size=0.02)
    px_al = pd.concat([prices[stocks], hedges], axis=1)
    for cost in (0.0005, 0.001):
        bt = run_backtest(px_al, w_al, cost)
        rows += summarise(f"A. Avellaneda-Lee ({cost * 1e4:.0f} bps)", bt.net_returns, bt.gross_returns,
                          bt.weights, spy)
        if cost == 0.0005:
            print(f"A. AL turnover/yr: {bt.turnover.sum() / len(bt.turnover) * 252:.1f}")

    # --- B. ETF pairs ------------------------------------------------------
    groups = {t: g for g, ts in ETF_GROUPS.items() for t in ts if t in etf_px.columns}
    etf_trade = etf_px[list(groups)]
    res_b = run_pair_portfolio(etf_trade, groups, top_k=10, max_pairs_per_stock=2)
    for cost in (0.0005, 0.001):
        bt = run_backtest(etf_trade, res_b.weights, cost)
        rows += summarise(f"B. ETF pairs ({cost * 1e4:.0f} bps)", bt.net_returns, bt.gross_returns,
                          bt.weights, spy)

    # --- C. Stock pairs (reference) -----------------------------------------
    sub = dict(zip(gics["ticker"], gics["sub_industry"]))
    comp = dict(zip(gics["ticker"], gics["company"]))
    sp_px = prices[[t for t in stocks if t in sub]]
    res_c = run_pair_portfolio(sp_px, sub, universe=membership_mask(spells, sp_px.index, sp_px.columns),
                               companies=comp)
    bt = run_backtest(sp_px, res_c.weights, 0.001)
    rows += summarise("C. Stock pairs (10 bps)", bt.net_returns, bt.gross_returns, bt.weights, spy)

    table = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(table.round(3).to_string(index=False))

    fmt = table.copy()
    for c in ["cagr_net", "vol", "max_dd", "gross_exposure"]:
        fmt[c] = fmt[c].map(lambda v: f"{v:.1%}")
    for c in ["sharpe_gross", "sharpe_net", "beta_spy"]:
        fmt[c] = fmt[c].map(lambda v: f"{v:.2f}")
    top_etf_pairs = (res_b.selections.assign(pair=lambda d: d["a"] + "/" + d["b"])["pair"]
                     .value_counts().head(10))
    OUT.mkdir(exist_ok=True)
    (OUT / "edge_search.md").write_text(
        "# Edge search with pre-registered parameters\n\n"
        "- **A. Avellaneda-Lee (2010)** residual reversion: 60-day regression on the stock's SPDR sector "
        "ETF, OU fit of cumulative residuals, open |s| > 1.25, close long s > −0.5 / short s < 0.75, "
        "κ > 252/30; 2% of capital per position; point-in-time S&P 500. Parameters from the paper, "
        "untouched. (XLRE/XLC are spliced with SPY returns before their launch.)\n"
        "- **B. ETF pairs**: the quarterly-reselected pair portfolio on "
        f"{len(groups)} liquid ETFs, pairs only within asset groups, top 10.\n"
        "- **C. Stock pairs**: reference from reports/pair_portfolio.md.\n\n"
        + fmt.to_markdown(index=False)
        + "\n\n## Most frequently selected ETF pairs\n\n" + top_etf_pairs.to_frame("quarters").to_markdown()
        + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUT / 'edge_search.md'}")


if __name__ == "__main__":
    main()
