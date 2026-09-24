"""Residual mean-reversion stat-arb (Avellaneda & Lee, 2010).

Each stock's daily returns are regressed on its sector ETF over a trailing
window; the cumulative residual X is modelled as an Ornstein-Uhlenbeck
process fitted by AR(1):  X_{k+1} = a + b X_k + e.

    kappa   = -ln(b) * 252            speed of mean reversion
    m       = a / (1 - b)             equilibrium level
    sigma_eq = sqrt(var(e) / (1 - b^2))
    s-score = (X_t - m) / sigma_eq

Trading rules from the paper (fixed, not tuned here):
    open  long  s < -1.25     close long  s > -0.50
    open  short s > +1.25     close short s < +0.75
    only when kappa > 252 / 30 (mean reversion faster than ~30 days).

A long position is +1 unit of the stock and -beta units of its ETF, so it is
market- and sector-neutral by construction; many small positions mean one
company's collapse is a small loss, not a portfolio event.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def s_scores(
    stock_rets: pd.DataFrame,
    etf_rets: pd.DataFrame,
    window: int = 60,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Daily s-scores, betas and kappas (dates x stocks), using data up to t.

    ``etf_rets`` must be aligned with ``stock_rets`` column-for-column: the
    hedge ETF's returns for each stock.
    """
    R = stock_rets.to_numpy()
    F = etf_rets.to_numpy()
    n_days, n = R.shape
    s_out = np.full((n_days, n), np.nan)
    b_out = np.full((n_days, n), np.nan)
    k_out = np.full((n_days, n), np.nan)

    for t in range(window, n_days):
        r = R[t - window + 1 : t + 1]
        f = F[t - window + 1 : t + 1]
        ok = ~(np.isnan(r).any(axis=0) | np.isnan(f).any(axis=0))
        if not ok.any():
            continue
        r, f = r[:, ok], f[:, ok]
        fm, rm = f.mean(axis=0), r.mean(axis=0)
        var_f = ((f - fm) ** 2).sum(axis=0)
        beta = ((f - fm) * (r - rm)).sum(axis=0) / np.where(var_f > 0, var_f, np.nan)
        alpha = rm - beta * fm
        eps = r - alpha - beta * f
        x = np.cumsum(eps, axis=0)

        x0, x1 = x[:-1], x[1:]
        x0m, x1m = x0.mean(axis=0), x1.mean(axis=0)
        var0 = ((x0 - x0m) ** 2).sum(axis=0)
        b = ((x0 - x0m) * (x1 - x1m)).sum(axis=0) / np.where(var0 > 0, var0, np.nan)
        a = x1m - b * x0m
        resid = x1 - a - b * x0
        valid = (b > 0) & (b < 1)
        with np.errstate(invalid="ignore", divide="ignore"):
            kappa = np.where(valid, -np.log(b) * 252, np.nan)
            m = np.where(valid, a / (1 - b), np.nan)
            sigma_eq = np.sqrt(resid.var(axis=0) / (1 - b**2))
            s = (x[-1] - m) / sigma_eq

        cols = np.flatnonzero(ok)
        s_out[t, cols] = s
        b_out[t, cols] = beta
        k_out[t, cols] = kappa

    idx, names = stock_rets.index, stock_rets.columns
    return (pd.DataFrame(s_out, idx, names), pd.DataFrame(b_out, idx, names),
            pd.DataFrame(k_out, idx, names))


def residual_reversion(
    prices: pd.DataFrame,
    hedge_map: dict[str, str],
    etf_prices: pd.DataFrame,
    universe: pd.DataFrame | None = None,
    window: int = 60,
    s_open: float = 1.25,
    s_close_long: float = 0.50,
    s_close_short: float = 0.75,
    min_kappa: float = 252 / 30,
    position_size: float = 0.02,
    s_smooth: int = 1,
    trade_every: int = 1,
    neutralize_with: str | None = None,
    scores: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Target weights over stocks *and* hedge ETFs (columns = stocks + ETFs).

    ``hedge_map`` maps each stock to its hedge ETF column in ``etf_prices``.
    ``position_size`` is the capital per open stock position (0.02 -> up to 50
    positions per unit of stock-side exposure).

    Turnover controls (all off by default = the paper's rules):
    ``s_smooth``        EMA span applied to the s-score (damps day-to-day flicker)
    ``trade_every``     evaluate entries/exits only every k-th day
    ``neutralize_with`` an ETF column (e.g. "SPY") used to make the whole book
                        dollar-neutral, removing residual market exposure
    ``scores``          precomputed ``s_scores`` output, to reuse across variants
    """
    stocks = [c for c in prices.columns if c in hedge_map and hedge_map[c] in etf_prices.columns]
    if scores is None:
        rets = prices[stocks].pct_change(fill_method=None)
        etf_rets = etf_prices.pct_change(fill_method=None)
        hedge = pd.DataFrame({s: etf_rets[hedge_map[s]] for s in stocks}, index=prices.index)
        scores = s_scores(rets, hedge, window)
    s, beta, kappa = (x.reindex(columns=stocks) for x in scores)
    if s_smooth > 1:
        s = s.ewm(span=s_smooth, min_periods=1).mean().where(s.notna())

    eligible = kappa.gt(min_kappa) & s.notna()
    if universe is not None:
        eligible &= universe.reindex(index=prices.index, columns=stocks, fill_value=False)

    S, B, E = s.to_numpy(), beta.to_numpy(), eligible.to_numpy()
    tradable = prices[stocks].notna().to_numpy()
    n_days, n = S.shape
    pos = np.zeros(n)
    stock_w = np.zeros((n_days, n))
    hedge_beta = np.zeros(n)
    etf_cols = list(etf_prices.columns)
    etf_idx = np.array([etf_cols.index(hedge_map[c]) for c in stocks])
    etf_w = np.zeros((n_days, len(etf_cols)))
    neutral_idx = etf_cols.index(neutralize_with) if neutralize_with else None

    for t in range(n_days):
        st = S[t]
        dead = ~tradable[t] | np.isnan(st)
        pos[(pos != 0) & dead] = 0  # forced exits happen any day
        if t % trade_every == 0:
            close_long = (pos > 0) & (st > -s_close_long)
            close_short = (pos < 0) & (st < s_close_short)
            pos[close_long | close_short] = 0
            flat = pos == 0
            go_long = flat & E[t] & (st < -s_open)
            go_short = flat & E[t] & (st > s_open)
            pos[go_long] = 1
            pos[go_short] = -1
            new = go_long | go_short
            hedge_beta[new] = B[t, new]
        hedge_beta[pos == 0] = 0.0

        stock_w[t] = pos * position_size
        np.add.at(etf_w[t], etf_idx, -pos * hedge_beta * position_size)
        if neutral_idx is not None:
            etf_w[t, neutral_idx] -= stock_w[t].sum() + etf_w[t].sum()

    weights = pd.concat(
        [pd.DataFrame(stock_w, prices.index, stocks), pd.DataFrame(etf_w, prices.index, etf_cols)], axis=1
    )
    # Only emit rows where the book changes; holdings drift in between.
    changed = weights.diff().abs().sum(axis=1).gt(1e-12)
    changed.iloc[0] = True
    return weights.where(changed, np.nan)
