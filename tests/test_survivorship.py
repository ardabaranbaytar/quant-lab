import numpy as np
import pandas as pd
import pytest

from quantlab.engine import delisting_days, ffill_within_life, run_backtest
from quantlab.strategies import cross_sectional_momentum
from quantlab.universe import (
    coverage_report,
    current_members,
    ever_members,
    members_on,
    membership_mask,
    normalise_spells,
)


@pytest.fixture
def spells():
    return normalise_spells(pd.DataFrame({
        "ticker": ["AAA", "BBB", "CCC", "BRK.B", "AAA"],
        "start_date": ["2020-01-01", "2020-01-01", "2021-01-01", "2020-01-01", "2022-06-01"],
        "end_date": ["2021-01-01", None, None, None, None],
    }))


def test_membership_queries(spells):
    assert members_on(spells, "2020-06-01") == ["AAA", "BBB", "BRK-B"]
    assert members_on(spells, "2021-01-01") == ["BBB", "BRK-B", "CCC"]  # AAA removed that day
    assert members_on(spells, "2022-07-01") == ["AAA", "BBB", "BRK-B", "CCC"]  # AAA re-added
    assert current_members(spells) == ["AAA", "BBB", "BRK-B", "CCC"]
    assert ever_members(spells, "2020-01-01", "2020-12-31") == ["AAA", "BBB", "BRK-B"]


def test_membership_mask_handles_repeat_spells(spells):
    idx = pd.bdate_range("2020-01-01", "2023-01-01")
    mask = membership_mask(spells, idx)
    assert mask.loc["2020-06-01", "AAA"] and not mask.loc["2021-06-01", "AAA"]
    assert mask.loc["2022-07-01", "AAA"]
    assert not mask.loc["2020-06-01", "CCC"]


def test_ffill_within_life_does_not_resurrect_dead_stocks():
    px = pd.DataFrame({"A": [np.nan, 1.0, np.nan, 2.0, np.nan, np.nan]})
    out = ffill_within_life(px)["A"].tolist()
    assert np.isnan(out[0])                    # not listed yet
    assert out[1:4] == [1.0, 1.0, 2.0]         # gap inside life filled
    assert np.isnan(out[4]) and np.isnan(out[5])  # dead stays dead


def test_delisting_days_ignore_short_vendor_lag():
    idx = pd.bdate_range("2020-01-01", periods=30)
    px = pd.DataFrame({"DEAD": 1.0, "LAG": 1.0, "OK": 1.0, "EMPTY": np.nan}, index=idx)
    px.loc[idx[10]:, "DEAD"] = np.nan
    px.loc[idx[-2]:, "LAG"] = np.nan
    days = delisting_days(px)
    assert list(days.index) == ["DEAD"] and days["DEAD"] == idx[10]


@pytest.mark.parametrize("policy,expected", [("last_price", 1.0), ("shumway", 0.7), ("total_loss", 0.0), (-0.5, 0.5)])
def test_delisting_return_policies(policy, expected):
    idx = pd.bdate_range("2020-01-01", periods=30)
    px = pd.DataFrame({"DEAD": 10.0}, index=idx)
    px.loc[idx[10]:, "DEAD"] = np.nan
    w = pd.DataFrame(1.0, index=idx, columns=["DEAD"])  # keeps trying to buy it
    res = run_backtest(px, w, cost_rate=0.0, delisting=policy)
    assert res.equity.iloc[-1] == pytest.approx(expected)
    assert (res.weights.loc[idx[10]:, "DEAD"] == 0).all()  # can't be bought after death
    assert res.delistings["ticker"].tolist() == ["DEAD"]


def test_delisted_leg_moves_to_cash_while_survivor_keeps_trading():
    idx = pd.bdate_range("2020-01-01", periods=30)
    px = pd.DataFrame({"DEAD": 10.0, "LIVE": np.linspace(10, 13, 30)}, index=idx)
    px.loc[idx[10]:, "DEAD"] = np.nan
    w = pd.DataFrame(np.nan, index=idx, columns=px.columns)
    w.iloc[0] = [0.5, 0.5]
    res = run_backtest(px, w, cost_rate=0.0, delisting="total_loss")
    live_growth = px["LIVE"].iloc[-1] / px["LIVE"].iloc[0]
    assert res.equity.iloc[-1] == pytest.approx(0.5 * live_growth)
    assert res.delistings["ticker"].tolist() == ["DEAD"]  # recorded although the policy is -100%


def test_total_loss_wipeout_keeps_weights_finite():
    # Everything held dies at -100% on the same day while LIVE is held at zero: nothing is left
    # to hold, and 0/0 must not leak NaN weights/turnover into later days.
    idx = pd.bdate_range("2020-01-01", periods=30)
    px = pd.DataFrame({"DEAD": 10.0, "LIVE": np.linspace(10, 13, 30)}, index=idx)
    px.loc[idx[10]:, "DEAD"] = np.nan
    w = pd.DataFrame({"DEAD": 1.0, "LIVE": 0.0}, index=idx)
    res = run_backtest(px, w, cost_rate=0.001, delisting="total_loss")
    assert np.isfinite(res.weights.to_numpy()).all()
    assert np.isfinite(res.turnover.to_numpy()).all()
    assert res.equity.iloc[-1] == pytest.approx(0.0)
    assert res.delistings["ticker"].tolist() == ["DEAD"]


def test_momentum_only_picks_point_in_time_members(prices):
    mask = pd.DataFrame(True, index=prices.index, columns=prices.columns)
    mask.loc[: prices.index[400], "A"] = False  # A joins the index late
    w = cross_sectional_momentum(prices, lookback=60, top_n=2, universe=mask)
    held_early = w.loc[: prices.index[400]].dropna(how="all")
    assert (held_early["A"] == 0).all()
    assert (w.loc[prices.index[401]:].dropna(how="all")["A"] > 0).any()


def test_coverage_report_counts_members_without_prices(spells):
    idx = pd.bdate_range("2020-01-01", "2020-03-01")
    mask = membership_mask(spells, idx)
    px = pd.DataFrame(1.0, index=idx, columns=["AAA", "BBB"])  # vendor lacks BRK-B
    rep = coverage_report(mask, px)
    assert rep["members"].iloc[0] == 3 and rep["with_prices"].iloc[0] == 2
    assert rep["coverage"].iloc[0] == pytest.approx(2 / 3)
