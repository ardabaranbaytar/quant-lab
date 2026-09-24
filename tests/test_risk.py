import numpy as np
import pandas as pd
import pytest

from quantlab.engine import run_backtest
from quantlab.risk import BROKEN, NORMAL, BreakMonitor, compute_detectors
from quantlab.risk.detectors import DETECTORS, cusum, rolling_dickey_fuller
from quantlab.risk.monitor import calibrate
from quantlab.risk.synthetic import SCENARIOS, generate_pair
from quantlab.strategies import pairs_trading


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_generator_is_reproducible_and_positive(scenario):
    a = generate_pair(scenario, seed=3).prices
    b = generate_pair(scenario, seed=3).prices
    pd.testing.assert_frame_equal(a, b)
    assert (a > 0).all().all()


def test_dickey_fuller_separates_stationary_from_random_walk():
    rng = np.random.default_rng(0)
    n = 2000
    ar = np.zeros(n)
    for t in range(1, n):
        ar[t] = 0.9 * ar[t - 1] + rng.normal()
    rw = np.cumsum(rng.normal(size=n))
    t_ar, hl_ar = rolling_dickey_fuller(pd.Series(ar), 250)
    t_rw, _ = rolling_dickey_fuller(pd.Series(rw), 250)
    assert t_ar.median() < -3 < t_rw.median()
    assert hl_ar.median() == pytest.approx(np.log(2) / 0.1, rel=0.3)


def test_cusum_ignores_short_spikes_but_accumulates_persistent_shift():
    z = pd.Series(np.zeros(200))
    spike = z.copy()
    spike.iloc[50:53] = 4.0
    shift = z.copy()
    shift.iloc[50:] = 3.0
    assert cusum(spike).max() < 10
    assert cusum(shift).iloc[-1] > 100


def test_detectors_are_causal():
    px = generate_pair("death", seed=1).prices
    cut = 900
    full = compute_detectors(px["A"], px["B"])
    shocked = px.copy()
    shocked.iloc[cut + 1 :] *= 0.5
    part = compute_detectors(shocked["A"], shocked["B"])
    pd.testing.assert_frame_equal(full.iloc[: cut + 1], part.iloc[: cut + 1])


def test_monitor_flags_dying_company_and_not_stable_pair():
    mon = BreakMonitor()
    death = generate_pair("death", seed=5)
    state = mon.evaluate_pair(death.prices["A"], death.prices["B"])["state"]
    assert (state.loc[death.break_date:] == BROKEN).any()
    stable = generate_pair("stable", seed=5).prices
    assert (mon.evaluate_pair(stable["A"], stable["B"])["state"].iloc[400:] != BROKEN).all()


def test_monitor_cooldown_reenables_pair():
    mon = BreakMonitor(cooldown=5, confirm_days=1, confirm_window=1)
    idx = pd.RangeIndex(30)
    scores = pd.DataFrame({d: 0.0 for d in DETECTORS}, index=idx)
    for d in DETECTORS:
        scores[d] = -1e9
    scores.loc[10:12, DETECTORS] = 1e9  # everything fires for 3 days
    state = mon.run(scores)["state"]
    assert state[9] == NORMAL and state[10] == BROKEN
    assert state[16] == BROKEN and state[18] == NORMAL  # 5 quiet days after day 12


def test_calibrate_returns_threshold_per_detector():
    pairs = [generate_pair("stable", seed=i).prices for i in range(3)]
    null = [compute_detectors(p["A"], p["B"]) for p in pairs]
    th = calibrate(null, 0.95)
    assert set(th) == set(DETECTORS)


def test_monitor_exits_pairs_trade_on_death_and_cuts_loss():
    pair = generate_pair("death", seed=11)
    px = pair.prices
    naive = pairs_trading(px, "A", "B", z_window=60)
    guarded = pairs_trading(px, "A", "B", z_window=60, break_monitor=BreakMonitor())
    after = px.index >= pair.break_date
    # Once broken, the guarded strategy holds nothing for the rest of the path.
    tail = guarded.loc[after].iloc[-100:]
    assert (tail.fillna(0).abs().sum(axis=1) == 0).all()
    assert naive.loc[after].fillna(0).abs().sum(axis=1).sum() > 0  # naive keeps trading it


def test_monitor_cuts_tail_loss_across_dying_companies():
    """Per path either side can win (naive may be short the dying leg); the
    claim is about the tail: the worst outcome must be much less bad."""
    naive, guarded = [], []
    for seed in range(20):
        px = generate_pair("death", seed=seed).prices
        for out, kw in ((naive, {}), (guarded, {"break_monitor": BreakMonitor()})):
            w = pairs_trading(px, "A", "B", z_window=60, **kw)
            out.append(float(run_backtest(px, w).equity.iloc[-1]))
    assert min(guarded) > min(naive) + 0.2


def test_stop_does_not_immediately_reenter(cointegrated_pair):
    w = pairs_trading(cointegrated_pair, hedge_window=120, z_window=60, entry_z=1.0, stop_z=1.5)
    held = w.dropna(how="all").abs().sum(axis=1) > 0
    assert held.any()
