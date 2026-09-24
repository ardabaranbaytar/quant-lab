import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from quantlab.ml import FEATURES, build_episodes, walk_forward_predict
from quantlab.risk.synthetic import generate_pair
from quantlab.strategies.pair_portfolio import run_pair_portfolio


@pytest.fixture(scope="module")
def pair_setup():
    px = generate_pair("stable", seed=21, n_days=1500).prices
    res = run_pair_portfolio(px, {"A": "g", "B": "g"}, formation_days=756, top_k=1)
    market = px["B"].pct_change()
    return px, res, market


def test_episodes_have_all_features_and_consistent_labels(pair_setup):
    px, res, market = pair_setup
    eps = build_episodes(px, res.selections, market)
    assert len(eps) > 5
    assert set(FEATURES) <= set(eps.columns)
    assert (eps["label"] == (eps["pnl"] > 0).astype(int)).all()
    assert (eps["exit_date"] >= eps["entry_date"]).all()
    assert (eps["abs_z"] > 2.0).all()


def test_episode_features_do_not_look_ahead(pair_setup):
    px, res, market = pair_setup
    eps = build_episodes(px, res.selections, market)
    cut = eps["entry_date"].iloc[len(eps) // 2]
    shocked = px.copy()
    shocked.loc[shocked.index > cut] *= 1.25
    eps2 = build_episodes(shocked, res.selections, shocked["B"].pct_change())
    before = eps[eps["entry_date"] <= cut].set_index(["a", "b", "entry_date"])[FEATURES]
    after = eps2.set_index(["a", "b", "entry_date"]).reindex(before.index)[FEATURES]
    pd.testing.assert_frame_equal(before, after)


def test_walk_forward_purges_unfinished_trades():
    rng = np.random.default_rng(0)
    n = 600
    entry = pd.Timestamp("2015-01-01") + pd.to_timedelta(rng.integers(0, 365 * 4, n), unit="D")
    eps = pd.DataFrame({
        "entry_date": entry,
        "exit_date": entry + pd.Timedelta(days=40),
        "x": rng.normal(size=n),
    })
    eps["label"] = (eps["x"] + rng.normal(scale=0.5, size=n) > 0).astype(int)
    eps["pnl"] = eps["label"] - 0.5

    seen = []

    class Spy(LogisticRegression):
        def fit(self, X, y):
            seen.append(X.index)
            return super().fit(X, y)

    pred = walk_forward_predict(eps, ["x"], Spy, first_test_year=2017, min_train=50)
    assert set(pred["fold"]) == {2017, 2018}
    for fold_year, train_idx in zip(sorted(pred["fold"].unique()), seen):
        assert (eps.loc[train_idx, "exit_date"] < pd.Timestamp(f"{fold_year}-01-01")).all()
    assert (pred["prob"][pred["x"] > 1].mean()) > 0.7  # learns a real signal when there is one


def test_entry_filter_vetoes_trades(pair_setup):
    px, _, _ = pair_setup
    none = run_pair_portfolio(px, {"A": "g", "B": "g"}, formation_days=756, top_k=1,
                              entry_filter=lambda a, b, d: False)
    held = none.weights.dropna(how="all").abs().sum(axis=1)
    assert (held == 0).all()
