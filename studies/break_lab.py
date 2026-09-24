"""Break lab: score the break monitor on synthetic pairs with known truth.

Usage:
    python -m studies.break_lab --calibrate   # print thresholds from stable pairs
    python -m studies.break_lab               # full evaluation -> reports/break_lab.md
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantlab.engine import index_position, run_backtest
from quantlab.risk.detectors import DETECTORS, compute_detectors
from quantlab.risk.monitor import BROKEN, BreakMonitor, calibrate
from quantlab.risk.synthetic import BREAK_SCENARIOS, SCENARIOS, generate_pair
from quantlab.strategies import pairs_trading

N_PATHS = 100
DETECT_WINDOW = 126   # a break counts as caught if flagged within ~6 months
WARMUP = 400          # detectors need ~1.5y of history
OUT = Path("reports")


def calibrate_thresholds(n: int = 200) -> dict[str, float]:
    null = [compute_detectors(p.prices["A"], p.prices["B"]).iloc[WARMUP:]
            for p in (generate_pair("stable", seed=10_000 + i) for i in range(n))]
    return calibrate(null)


def evaluate(monitor: BreakMonitor, n_paths: int = N_PATHS) -> tuple[pd.DataFrame, pd.DataFrame]:
    detect_rows, pnl_rows = [], []
    for scenario in SCENARIOS:
        for i in range(n_paths):
            pair = generate_pair(scenario, seed=i)
            px = pair.prices
            mon = monitor.evaluate_pair(px["A"], px["B"])
            idx = px.index
            broken = mon["state"] == BROKEN
            live = idx >= idx[WARMUP]
            b = pair.break_date

            before = broken & live & ((idx < b) if b is not None else True)
            row: dict[str, Any] = {"scenario": scenario, "false_alarm": bool(before.any())}
            if b is not None:
                after = broken[(idx >= b)]
                first = pd.Timestamp(after.index[int(np.argmax(after.to_numpy()))]) if after.any() else None
                delay = index_position(idx, first) - index_position(idx, b) if first is not None else None
                row["flagged_after"] = first is not None
                row["delay"] = delay
                row["caught"] = delay is not None and delay <= DETECT_WINDOW
                row["fired"] = ",".join(d for d in DETECTORS if mon.at[first, d]) if first is not None else ""
            detect_rows.append(row)

            # P&L: same pairs strategy, three risk settings.
            variants = {
                "naive": pairs_trading(px, "A", "B", z_window=60),
                "z_stop_4": pairs_trading(px, "A", "B", z_window=60, stop_z=4.0),
                "monitor": pairs_trading(px, "A", "B", z_window=60, break_monitor=monitor),
            }
            for name, w in variants.items():
                res = run_backtest(px, w, cost_rate=0.001)
                r = res.net_returns.loc[idx[WARMUP]:]
                pnl_rows.append({"scenario": scenario, "variant": name,
                                 "total_return": float(np.prod(1 + r.to_numpy()) - 1)})
    return pd.DataFrame(detect_rows), pd.DataFrame(pnl_rows)


def summarise(detect: pd.DataFrame, pnl: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for scenario, g in detect.groupby("scenario", sort=False):
        is_break = scenario in BREAK_SCENARIOS
        row = {
            "scenario": scenario,
            "type": "break" if is_break else "no break",
            "false_alarm_rate": g["false_alarm"].mean(),
        }
        if is_break:
            row["caught_within_6m"] = g["caught"].mean()
            row["median_delay_days"] = g["delay"].dropna().median()
        elif scenario == "temp_shock":
            # Flagging a temporary shock = missed opportunity.
            row["false_alarm_rate"] = (g["false_alarm"] | g["flagged_after"]).mean()
        rows.append(row)
    det = pd.DataFrame(rows)

    def cvar5(x):
        return x[x <= x.quantile(0.05)].mean()

    p = pnl.groupby(["scenario", "variant"], sort=False)["total_return"].agg(
        mean="mean", median="median", worst_5pct=cvar5
    ).reset_index()
    return det, p


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--paths", type=int, default=N_PATHS)
    args = parser.parse_args()

    if args.calibrate:
        th = calibrate_thresholds()
        print({k: round(v, 3) for k, v in th.items()})
        return

    monitor = BreakMonitor()
    detect, pnl = evaluate(monitor, args.paths)
    det, p = summarise(detect, pnl)
    fired = (detect.loc[detect["fired"].fillna("") != "", "fired"].str.split(",").explode()
             .value_counts().rename("times_in_first_break_vote"))

    pd.set_option("display.width", 200)
    print(det.round(3).to_string(index=False))
    print(p.round(3).to_string(index=False))
    print(fired.to_string())

    OUT.mkdir(exist_ok=True)
    pct = lambda s: s.map(lambda v: "—" if pd.isna(v) else f"{v:.0%}")
    det_fmt = det.copy()
    for c in ["false_alarm_rate", "caught_within_6m"]:
        det_fmt[c] = pct(det_fmt[c])
    det_fmt["median_delay_days"] = det_fmt["median_delay_days"].map(
        lambda v: "—" if pd.isna(v) else f"{v:.0f}")
    p_fmt = p.copy()
    for c in ["mean", "median", "worst_5pct"]:
        p_fmt[c] = p_fmt[c].map(lambda v: f"{v:+.1%}")
    (OUT / "break_lab.md").write_text(
        f"# Break lab ({args.paths} synthetic pairs per scenario)\n\n"
        "## Detection\n\n" + det_fmt.to_markdown(index=False)
        + "\n\nA break is *caught* if flagged BROKEN within 126 trading days. "
        "False alarm = BROKEN before the break (or at any time for pairs that never break; "
        "for temporary shocks, flagging the shock itself counts as a false alarm — a missed opportunity).\n\n"
        "## P&L of the same pairs strategy under three risk settings\n\n"
        "Total return after the warm-up; worst_5pct = mean of the worst 5% of paths (CVaR).\n\n"
        + p_fmt.to_markdown(index=False)
        + "\n\n## Detectors present in the first BROKEN vote\n\n" + fired.to_frame().to_markdown()
        + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUT / 'break_lab.md'}")


if __name__ == "__main__":
    main()
