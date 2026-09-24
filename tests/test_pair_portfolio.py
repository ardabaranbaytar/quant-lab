import numpy as np
import pandas as pd
import pytest

from quantlab.engine import run_backtest
from quantlab.risk import BreakMonitor
from quantlab.risk.synthetic import generate_pair
from quantlab.strategies.pair_portfolio import pair_portfolio, run_pair_portfolio, select_pairs


@pytest.fixture
def universe_prices():
    """Two cointegrated pairs + two unrelated random walks, over ~6 years."""
    p1 = generate_pair("stable", seed=1, n_days=1500).prices.rename(columns={"A": "A1", "B": "B1"})
    p2 = generate_pair("stable", seed=2, n_days=1500).prices.rename(columns={"A": "A2", "B": "B2"})
    rng = np.random.default_rng(9)
    noise = pd.DataFrame(50 * np.exp(np.cumsum(rng.normal(0, 0.015, (1500, 2)), axis=0)),
                         index=p1.index, columns=["R1", "R2"])
    return pd.concat([p1, p2, noise], axis=1)


def test_select_pairs_finds_true_pairs_within_groups(universe_prices):
    window = np.log(universe_prices.iloc[:756])
    groups = {"A1": "g1", "B1": "g1", "A2": "g2", "B2": "g2", "R1": "g1", "R2": "g2"}
    chosen = select_pairs(window, groups, top_k=5)
    found = {tuple(sorted((r.a, r.b))) for r in chosen.itertuples()}
    assert ("A1", "B1") in found and ("A2", "B2") in found
    assert not any("R1" in p and "R2" in p for p in found)  # cross-group never tested


def test_max_pairs_per_stock_is_respected(universe_prices):
    window = np.log(universe_prices.iloc[:756])
    chosen = select_pairs(window, {c: "all" for c in window.columns}, max_pvalue=1.0,
                          half_life_range=(0, np.inf), top_k=10, max_pairs_per_stock=1)
    legs = pd.concat([chosen["a"], chosen["b"]])
    assert legs.value_counts().max() == 1


def test_portfolio_is_causal_and_market_neutral(universe_prices):
    groups = {"A1": "g1", "B1": "g1", "A2": "g2", "B2": "g2", "R1": "g1", "R2": "g2"}
    kw = {"groups": groups, "formation_days": 500, "trading_days": 63, "top_k": 2, "max_pairs_per_stock": 1}
    full = pair_portfolio(universe_prices, **kw)
    shocked = universe_prices.copy()
    shocked.iloc[801:] *= 1.3
    part = pair_portfolio(shocked, **kw)
    pd.testing.assert_frame_equal(full.iloc[:801], part.iloc[:801])
    active = full.dropna(how="all")
    assert (active.abs().sum(axis=1) <= 1 + 1e-9).all()      # never levered
    # Legs are sized 1 : beta (hedge-ratio neutral, not dollar neutral), so the
    # short leg / long leg ratio of every open pair must equal -beta.
    res = run_pair_portfolio(universe_prices, **kw)
    starts = sorted(res.selections["period_start"].unique()) + [universe_prices.index[-1]]
    for sel in res.selections.itertuples():
        period_end = starts[starts.index(sel.period_start) + 1]
        period = active.loc[sel.period_start:period_end - pd.Timedelta(days=1)]
        open_rows = period[period[sel.a] != 0]
        if len(open_rows):
            ratio = (open_rows[sel.b] / open_rows[sel.a]).iloc[0]
            assert ratio == pytest.approx(-sel.beta, rel=1e-6)


def test_portfolio_trades_and_respects_universe(universe_prices):
    groups = {c: "all" for c in universe_prices.columns}
    mask = pd.DataFrame(True, index=universe_prices.index, columns=universe_prices.columns)
    mask[["A2", "B2"]] = False
    res = run_pair_portfolio(universe_prices, groups, universe=mask, formation_days=500, top_k=3)
    assert not res.selections.empty
    assert not res.selections[["a", "b"]].isin(["A2", "B2"]).any().any()
    bt = run_backtest(universe_prices, res.weights, cost_rate=0.0005)
    assert bt.equity.iloc[-1] > 1.0


def test_monitor_forces_exit_on_dying_leg():
    pair = generate_pair("death", seed=4, n_days=1500, break_at=1100).prices
    res = run_pair_portfolio(pair, {"A": "g", "B": "g"}, formation_days=756, top_k=1,
                             break_monitor=BreakMonitor())
    late = res.weights.loc[pair.index[1300]:].dropna(how="all")
    assert late.empty or (late.abs().sum(axis=1) == 0).all() or not res.risk_exits.empty
