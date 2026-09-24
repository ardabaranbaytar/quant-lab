import numpy as np
import pandas as pd

from quantlab.engine import run_backtest
from quantlab.strategies.residual_reversion import residual_reversion, s_scores


def make_market(n_days=1000, n_stocks=30, seed=0):
    """Stocks = beta * sector ETF + mean-reverting (AR(1)) idiosyncratic price noise."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n_days)
    etf = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n_days)))
    etf_px = pd.DataFrame({"ETF": etf}, index=idx)
    stocks = {}
    for i in range(n_stocks):
        beta = rng.uniform(0.7, 1.3)
        noise = np.zeros(n_days)
        for t in range(1, n_days):
            noise[t] = 0.85 * noise[t - 1] + rng.normal(0, 0.012)
        stocks[f"S{i}"] = 50 * np.exp(beta * np.log(etf / etf[0]) + noise)
    return pd.DataFrame(stocks, index=idx), etf_px


def test_s_scores_are_causal():
    px, etf = make_market(n_days=300, n_stocks=5)
    rets = px.pct_change()
    hedge = pd.DataFrame({c: etf["ETF"].pct_change() for c in px}, index=px.index)
    s1, _, _ = s_scores(rets, hedge)
    rets2 = rets.copy()
    rets2.iloc[201:] *= -3
    s2, _, _ = s_scores(rets2, hedge)
    pd.testing.assert_frame_equal(s1.iloc[:201], s2.iloc[:201])


def test_residual_reversion_profits_on_mean_reverting_residuals_and_is_hedged():
    px, etf = make_market()
    hedge_map = {c: "ETF" for c in px}
    w = residual_reversion(px, hedge_map, etf, position_size=0.05)
    all_px = pd.concat([px, etf], axis=1)
    res = run_backtest(all_px, w, cost_rate=0.0)
    assert res.equity.iloc[-1] > 1.1
    held = w.ffill().fillna(0)
    stock_exposure = held[px.columns].sum(axis=1)
    etf_exposure = held["ETF"]
    active = stock_exposure.abs() > 0
    # net beta-weighted exposure small relative to gross
    assert (stock_exposure[active] + etf_exposure[active]).abs().mean() < 0.5 * held.abs().sum(axis=1)[active].mean()


def test_universe_mask_blocks_entries():
    px, etf = make_market(n_days=400, n_stocks=6)
    mask = pd.DataFrame(False, index=px.index, columns=px.columns)
    w = residual_reversion(px, {c: "ETF" for c in px}, etf, universe=mask)
    assert w.fillna(0).abs().to_numpy().sum() == 0
