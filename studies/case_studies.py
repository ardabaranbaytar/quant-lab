"""Real-world break case studies for the break monitor.

Pairs where one company's story broke on a known date, plus healthy control
pairs that should *not* be flagged. Free data only, so the failures here are
companies that survived (the ones that went to zero are missing from Yahoo).

Usage:  python -m studies.case_studies   -> reports/case_studies.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from quantlab.data import clean_prices, load_prices
from quantlab.engine import index_position, run_backtest
from quantlab.metrics import performance_summary
from quantlab.risk import BROKEN, WARNING, BreakMonitor, compute_detectors
from quantlab.risk.monitor import calibrate
from quantlab.strategies import pairs_trading

START, END = "2010-01-01", "2024-12-31"
WARMUP = 400
EARLY = 250  # detection up to ~1 year before the headline date counts (troubles build up)
OUT = Path("reports")


@dataclass
class Case:
    a: str
    b: str
    event: str | None
    story: str


BREAKS = [
    Case("GE", "HON", "2017-10-20", "GE: earnings collapse, dividend cut"),
    Case("GE", "MMM", "2017-10-20", "GE: earnings collapse, dividend cut"),
    Case("WFC", "JPM", "2016-09-08", "Wells Fargo: fake-accounts scandal, 2018 asset cap"),
    Case("BA", "LMT", "2019-03-13", "Boeing: 737 MAX grounding"),
    Case("INTC", "TXN", "2020-07-23", "Intel: 7nm delay, lost process lead"),
    Case("KEY", "PNC", "2023-03-10", "KeyCorp: 2023 regional bank crisis"),
]
CONTROLS = [
    Case("KO", "PEP", None, "control"),
    Case("XOM", "CVX", None, "control"),
    Case("V", "MA", None, "control"),
    Case("HD", "LOW", None, "control"),
    Case("JPM", "BAC", None, "control"),
]

# Same-industry pairs used ONLY to calibrate thresholds on real data. None of
# their tickers appear in the test cases above, so the test is out-of-sample.
CALIBRATION_PAIRS = [
    ("DUK", "SO"), ("AEP", "XEL"), ("ED", "EIX"), ("WEC", "CMS"),
    ("COP", "EOG"), ("SLB", "HAL"), ("MPC", "VLO"), ("PSX", "VLO"),
    ("MS", "GS"), ("FITB", "HBAN"), ("RF", "HBAN"), ("USB", "MTB"),
    ("PG", "CL"), ("KMB", "CL"), ("GIS", "K"), ("MDLZ", "HSY"),
    ("MRK", "PFE"), ("ABT", "MDT"), ("BMY", "PFE"), ("AMGN", "GILD"),
    ("WMT", "TGT"), ("COST", "WMT"), ("MSFT", "ORCL"), ("ADI", "MCHP"),
    ("CAT", "DE"), ("UNP", "CSX"), ("NSC", "CSX"), ("UPS", "FDX"),
    ("EMR", "ETN"), ("PSA", "EXR"), ("O", "NNN"), ("T", "VZ"),
    ("TRV", "CB"), ("ALL", "PGR"), ("SHW", "PPG"),
]
THRESHOLDS_FILE = OUT / "real_thresholds.json"


def calibrate_on_real_pairs(prices: pd.DataFrame, quantile: float = 0.99) -> dict[str, float]:
    null = []
    for a, b in CALIBRATION_PAIRS:
        if a in prices and b in prices:
            px = prices[[a, b]].dropna()
            null.append(compute_detectors(px[a], px[b]).iloc[WARMUP:])
    return calibrate(null, quantile)


def analyse(case: Case, prices: pd.DataFrame, monitor: BreakMonitor) -> dict:
    px = prices[[case.a, case.b]].dropna()
    mon = monitor.evaluate_pair(px[case.a], px[case.b])
    idx = px.index
    state = mon["state"]
    live = idx >= idx[WARMUP]
    log_ratio = cast(pd.Series, np.log(px[case.a] / px[case.b]))

    row: dict[str, Any] = {"pair": f"{case.a}/{case.b}", "story": case.story}
    if case.event is None:
        row["broken_days"] = int(((state == BROKEN) & live).sum())
        row["warning_days"] = int(((state == WARNING) & live).sum())
    else:
        e = int(idx.searchsorted(pd.Timestamp(case.event)))
        ev = pd.Timestamp(idx[e])
        window = (idx >= idx[max(e - EARLY, WARMUP)]) & (idx <= idx[min(e + EARLY, len(idx) - 1)])
        hits = state[window & (state == BROKEN)]
        first = pd.Timestamp(hits.index[0]) if len(hits) else None
        false_before = ((state == BROKEN) & live & (idx < idx[max(e - EARLY, WARMUP)])).sum()
        one_year = idx[min(e + 252, len(idx) - 1)]
        row.update({
            "event": ev.date(),
            "first_broken": first.date() if first is not None else "not flagged",
            "delay_days": (index_position(idx, first) - e) if first is not None else None,
            "rel_move_to_flag": float(log_ratio[first] - log_ratio[ev]) if first is not None else None,
            "rel_move_1y": float(log_ratio[one_year] - log_ratio[ev]),
            "false_broken_days_before": int(false_before),
            "fired": ",".join(d for d in monitor.thresholds if first is not None and mon.loc[first, d]),
        })

    variants: dict[str, BreakMonitor | None] = {"naive": None, "monitor": monitor}
    for name, guard in variants.items():
        w = pairs_trading(px, case.a, case.b, z_window=60, break_monitor=guard)
        res = run_backtest(px, w, cost_rate=0.001)
        s = performance_summary(res.net_returns.loc[idx[WARMUP]:])
        row[f"{name}_return"] = s["total_return"]
        row[f"{name}_maxdd"] = s["max_drawdown"]
    return row


def main() -> None:
    tickers = sorted({t for c in BREAKS + CONTROLS for t in (c.a, c.b)}
                     | {t for pair in CALIBRATION_PAIRS for t in pair})
    prices = clean_prices(load_prices(tickers, START, END))

    real_th = calibrate_on_real_pairs(prices)
    OUT.mkdir(exist_ok=True)
    THRESHOLDS_FILE.write_text(json.dumps(real_th, indent=2))
    synthetic = BreakMonitor()
    th_table = pd.DataFrame({"synthetic": synthetic.thresholds, "real": real_th}).round(3)
    print(th_table.to_string())

    results = {}
    for label, monitor in {"synthetic": synthetic, "real": BreakMonitor(thresholds=real_th)}.items():
        results[label] = (
            pd.DataFrame([analyse(c, prices, monitor) for c in BREAKS]),
            pd.DataFrame([analyse(c, prices, monitor) for c in CONTROLS]),
        )
    breaks, controls = results["real"]
    syn_breaks, syn_controls = results["synthetic"]

    pd.set_option("display.width", 250)
    for label, (bk, ct) in results.items():
        print(f"\n=== thresholds calibrated on {label} pairs ===")
        print(bk.drop(columns=["story", "fired"]).round(3).to_string(index=False))
        print(ct.drop(columns=["story"]).round(3).to_string(index=False))

    def fmt(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for c in df.columns:
            if c.endswith(("_return", "_maxdd")) or c.startswith("rel_move"):
                df[c] = df[c].map(lambda v: "—" if pd.isna(v) else f"{v:+.1%}")
        return df

    summary = pd.DataFrame({
        label: {
            "breaks flagged (of 6)": int(bk["delay_days"].notna().sum()),
            "false BROKEN days before events": int(bk["false_broken_days_before"].sum()),
            "BROKEN days on controls": int(ct["broken_days"].sum()),
            "mean return on breaks: naive": f"{bk['naive_return'].mean():+.1%}",
            "mean return on breaks: monitor": f"{bk['monitor_return'].mean():+.1%}",
        }
        for label, (bk, ct) in results.items()
    })
    (OUT / "case_studies.md").write_text(
        f"# Break monitor on real pairs ({START[:4]}–{END[:4]})\n\n"
        "## Why two calibrations\n\n"
        "Thresholds calibrated on synthetic stable pairs flag healthy real pairs for hundreds "
        "of days: real spreads are far less well-behaved than an Ornstein-Uhlenbeck process. "
        f"Re-calibrating on {len(CALIBRATION_PAIRS)} same-industry pairs that share no ticker with "
        "the test cases (99th percentile per detector) swings to the other extreme: real pairs "
        "diverge so often that 'normal' becomes very wide and nothing is flagged. Neither "
        "calibration alone is usable.\n\n"
        + th_table.to_markdown()
        + "\n\n" + summary.to_markdown()
        + "\n\n## Known breaks (real-data thresholds)\n\n"
        "`delay_days`: trading days from the headline date to the first BROKEN flag "
        f"(negative = flagged before the headline; flags up to {EARLY} days early count). "
        "`rel_move_*`: change in log(A/B) from the event to the flag / to one year later — "
        "how much of the divergence had already happened when the monitor reacted.\n\n"
        + fmt(breaks).to_markdown(index=False)
        + "\n\n## Healthy controls (should not be flagged)\n\n"
        + fmt(controls).to_markdown(index=False)
        + "\n\n## For comparison: synthetic thresholds\n\n"
        + fmt(syn_breaks.drop(columns=["story"])).to_markdown(index=False)
        + "\n\n" + fmt(syn_controls.drop(columns=["story"])).to_markdown(index=False)
        + "\n\nPairs strategy: z-window 60, entry 2, exit 0, 3-year hedge ratio, 10 bps costs; "
        "returns after a 400-day warm-up.\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUT / 'case_studies.md'}")


if __name__ == "__main__":
    main()
