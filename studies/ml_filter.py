"""Can a model tell which spread divergences will revert?

1. Run the multi-pair portfolio to get quarterly pair selections.
2. Turn every entry signal into an episode (features at entry, net P&L outcome).
3. Walk-forward, purged: train on episodes closed before year Y, predict year Y.
4. Use the model as an entry filter in the portfolio and compare.

Usage:  python -m studies.ml_filter  -> reports/ml_filter.md
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from quantlab.data import clean_prices, load_prices
from quantlab.engine import run_backtest
from quantlab.metrics import performance_summary
from quantlab.ml import FEATURES, build_episodes, walk_forward_predict
from quantlab.strategies.pair_portfolio import run_pair_portfolio
from quantlab.universe import (
    current_members,
    ever_members,
    load_sp500_gics,
    load_sp500_spells,
    membership_mask,
)

START, END = "2010-01-01", "2024-12-31"
FIRST_TEST_YEAR = 2016
COST = 0.001
OUT = Path("reports")


def make_gbm():
    return HistGradientBoostingClassifier(
        max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=50,
        l2_regularization=1.0, random_state=0,
    )


def make_logit():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(C=0.1, max_iter=2000))


MODELS = {"logistic regression": make_logit, "gradient boosting": make_gbm}


def pct(v) -> str:
    return "—" if pd.isna(v) else f"{v:.1%}"


def evaluate_predictions(pred: pd.DataFrame) -> dict:
    take = pred["prob"] > pred["train_base_rate"]
    return {
        "test_episodes": len(pred),
        "auc": roc_auc_score(pred["label"], pred["prob"]),
        "base_hit_rate": pred["label"].mean(),
        "accepted_share": take.mean(),
        "hit_rate_accepted": pred.loc[take, "label"].mean(),
        "mean_pnl_all": pred["pnl"].mean(),
        "mean_pnl_accepted": pred.loc[take, "pnl"].mean(),
        "mean_pnl_rejected": pred.loc[~take, "pnl"].mean(),
    }


def yearly_quality(pred: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for year, g in pred.groupby("fold"):
        take = g["prob"] > g["train_base_rate"]
        rows[year] = {
            "episodes": len(g),
            "auc": roc_auc_score(g["label"], g["prob"]) if g["label"].nunique() > 1 else np.nan,
            "hit_all": g["label"].mean(),
            "hit_accepted": g.loc[take, "label"].mean(),
            "pnl_all": g["pnl"].mean(),
            "pnl_accepted": g.loc[take, "pnl"].mean(),
        }
    return pd.DataFrame(rows).T


def main() -> None:
    spells = load_sp500_spells()
    gics = load_sp500_gics()
    groups = dict(zip(gics["ticker"], gics["sub_industry"]))
    companies = dict(zip(gics["ticker"], gics["company"]))
    raw = load_prices(sorted(set(ever_members(spells, START, END)) | set(current_members(spells)) | {"SPY"}),
                      START, END)
    prices = clean_prices(raw)
    spy = prices.pop("SPY").pct_change()
    prices = prices[[t for t in prices.columns if t in groups and prices[t].notna().any()]]
    mask = membership_mask(spells, prices.index, prices.columns)

    cache: dict = {}
    base = run_pair_portfolio(prices, groups, universe=mask, companies=companies, selection_cache=cache)
    episodes = build_episodes(prices, base.selections, spy, cost_rate=COST)
    print(f"episodes: {len(episodes)} | profitable: {episodes['label'].mean():.1%} | "
          f"mean net pnl {episodes['pnl'].mean():+.2%}")

    results, preds = [], {}
    for name, factory in MODELS.items():
        pred = walk_forward_predict(episodes, FEATURES, factory, FIRST_TEST_YEAR)
        preds[name] = pred
        results.append({"model": name, **evaluate_predictions(pred)})

    # Placebo: same pipeline, labels shuffled within each year -> AUC must be ~0.5.
    rng = np.random.default_rng(0)
    shuffled = episodes.copy()
    shuffled["label"] = shuffled.groupby(shuffled["entry_date"].dt.year)["label"].transform(
        lambda s: rng.permutation(s.to_numpy()))
    placebo = walk_forward_predict(shuffled, FEATURES, make_gbm, FIRST_TEST_YEAR)
    placebo_auc = roc_auc_score(placebo["label"], placebo["prob"])

    table = pd.DataFrame(results)
    pd.set_option("display.width", 250)
    print(table.round(4).to_string(index=False))
    print(f"placebo AUC (shuffled labels): {placebo_auc:.3f}")

    gbm = preds["gradient boosting"]
    by_year = yearly_quality(gbm)
    print(by_year.round(3).to_string())

    # Portfolio with the model as entry filter (test years only).
    taken = gbm[gbm["prob"] > gbm["train_base_rate"]]
    approved = set(zip(taken["a"], taken["b"], taken["entry_date"]))
    test_start = pd.Timestamp(f"{FIRST_TEST_YEAR}-01-01")

    def ml_filter(a, b, date):
        return date < test_start or (a, b, date) in approved

    variants = {
        "all signals": base,
        "ML-filtered": run_pair_portfolio(prices, groups, universe=mask, companies=companies,
                                          selection_cache=cache, entry_filter=ml_filter),
    }
    port_rows, yearly = [], {}
    for name, res in variants.items():
        bt = run_backtest(prices, res.weights, COST)
        r = bt.net_returns.loc[test_start:]
        s = performance_summary(r)
        g = performance_summary(bt.gross_returns.loc[test_start:])
        port_rows.append({"portfolio": name, "sharpe_before_costs": g["sharpe"], "total_return": s["total_return"],
                          "cagr": s["cagr"], "volatility": s["volatility"], "sharpe": s["sharpe"],
                          "max_drawdown": s["max_drawdown"],
                          "avg_gross_exposure": bt.weights.loc[test_start:].abs().sum(axis=1).mean()})
        yearly[name] = (1 + r).groupby(pd.DatetimeIndex(r.index).year).prod() - 1
    port = pd.DataFrame(port_rows)
    print(port.round(3).to_string(index=False))

    # Which features carry the signal? Permutation importance on each test fold.
    imps = []
    for year in sorted(gbm["fold"].unique()):
        cutoff = pd.Timestamp(f"{year}-01-01")
        train = episodes[episodes["exit_date"] < cutoff]
        test = episodes[episodes["entry_date"].dt.year == year]
        if test["label"].nunique() < 2:
            continue
        model = make_gbm().fit(train[FEATURES], train["label"])
        pi = permutation_importance(model, test[FEATURES], test["label"], scoring="roc_auc",
                                    n_repeats=5, random_state=0)
        imps.append(pd.Series(pi.importances_mean, index=FEATURES))
    importance = pd.concat(imps, axis=1).mean(axis=1).sort_values(ascending=False)
    print(importance.round(4).head(10).to_string())

    # Robustness: learn from every cointegrated pair (top 100 per period, no
    # per-stock cap) instead of only the 20 traded ones -> ~3x more episodes.
    wide = run_pair_portfolio(prices, groups, universe=mask, companies=companies,
                              top_k=100, max_pairs_per_stock=100)
    wide_eps = build_episodes(prices, wide.selections, spy, cost_rate=COST)
    robust_rows = []
    for name, factory in MODELS.items():
        pred = walk_forward_predict(wide_eps, FEATURES, factory, FIRST_TEST_YEAR)
        robust_rows.append({"model": name, **evaluate_predictions(pred)})
    robust = pd.DataFrame(robust_rows)
    print(f"\nrobustness ({len(wide_eps)} episodes):")
    print(robust.round(4).to_string(index=False))

    def fmt_quality(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for c in ["base_hit_rate", "accepted_share", "hit_rate_accepted"]:
            df[c] = df[c].map(pct)
        for c in ["mean_pnl_all", "mean_pnl_accepted", "mean_pnl_rejected"]:
            df[c] = df[c].map(lambda v: f"{v:+.2%}")
        df["auc"] = df["auc"].map(lambda v: f"{v:.3f}")
        return df

    t = table.copy()
    for c in ["base_hit_rate", "accepted_share", "hit_rate_accepted"]:
        t[c] = t[c].map(pct)
    for c in ["mean_pnl_all", "mean_pnl_accepted", "mean_pnl_rejected"]:
        t[c] = t[c].map(lambda v: f"{v:+.2%}")
    t["auc"] = t["auc"].map(lambda v: f"{v:.3f}")
    pf = port.copy()
    for c in ["total_return", "cagr", "volatility", "max_drawdown", "avg_gross_exposure"]:
        pf[c] = pf[c].map(pct)
    for c in ["sharpe_before_costs", "sharpe"]:
        pf[c] = pf[c].map(lambda v: f"{v:.2f}")
    ya = by_year.copy()
    ya["episodes"] = ya["episodes"].astype(int)
    ya["auc"] = ya["auc"].map(lambda v: f"{v:.3f}")
    for c in ["hit_all", "hit_accepted"]:
        ya[c] = ya[c].map(pct)
    for c in ["pnl_all", "pnl_accepted"]:
        ya[c] = ya[c].map(lambda v: "—" if pd.isna(v) else f"{v:+.2%}")

    OUT.mkdir(exist_ok=True)
    (OUT / "ml_filter.md").write_text(
        f"# ML entry filter for pairs trading ({FIRST_TEST_YEAR}–{END[:4]} out-of-sample)\n\n"
        f"{len(episodes)} entry episodes from quarterly-selected S&P 500 pairs; "
        f"{episodes['label'].mean():.1%} profitable after {2 * COST * 1e4:.0f} bps round-trip costs. "
        "Walk-forward by calendar year, purged: each year's model sees only episodes that had "
        "closed before 1 January. A signal is taken when P(profit) exceeds the training base rate.\n\n"
        "## Prediction quality (all test years pooled)\n\n" + t.to_markdown(index=False)
        + f"\n\nPlacebo (labels shuffled within year, same pipeline): AUC **{placebo_auc:.3f}**.\n\n"
        "## Gradient boosting by test year\n\n" + ya.to_markdown()
        + "\n\n## Portfolio impact\n\n" + pf.to_markdown(index=False)
        + "\n\n" + pd.DataFrame(yearly).map(lambda v: f"{v:+.1%}").to_markdown()
        + "\n\n## Permutation importance (mean drop in test AUC)\n\n"
        + importance.round(4).to_frame("importance").to_markdown()
        + f"\n\n## Robustness: {len(wide_eps)} episodes from every cointegrated pair\n\n"
        "Training on ~3x more episodes (top 100 pairs per period) is the real test of whether "
        "the small-sample signal above is genuine.\n\n"
        + fmt_quality(robust).to_markdown(index=False)
        + "\n\n## Conclusion\n\n"
        "With these entry-time features, whether an individual pair trade ends in profit is "
        "essentially unpredictable: the modest AUC on the small dataset disappears on the larger "
        "one, and yearly AUC flips sign around the 2022 rate-regime change. The filter is not "
        "used by default.\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUT / 'ml_filter.md'}")


if __name__ == "__main__":
    main()
