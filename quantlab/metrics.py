"""Performance and risk metrics computed from a daily return series."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def drawdown(returns: pd.Series) -> pd.Series:
    equity = (1 + returns).cumprod()
    return equity / equity.cummax() - 1


def performance_summary(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    turnover: pd.Series | None = None,
    periods_per_year: int = TRADING_DAYS,
) -> dict[str, float]:
    """Standard metrics. ``risk_free_rate`` is annual (e.g. 0.03 for 3%)."""
    returns = returns.dropna()
    n = len(returns)
    if n == 0:
        raise ValueError("Empty return series")

    total_return = float(np.prod(1 + returns.to_numpy()) - 1)
    cagr = (1 + total_return) ** (periods_per_year / n) - 1
    vol = float(returns.std() * np.sqrt(periods_per_year))

    excess = returns - risk_free_rate / periods_per_year
    ex_std = excess.std()
    sharpe = float(excess.mean() / ex_std * np.sqrt(periods_per_year)) if ex_std > 0 else np.nan

    downside = excess.clip(upper=0)
    dd_std = np.sqrt((downside**2).mean())
    sortino = float(excess.mean() / dd_std * np.sqrt(periods_per_year)) if dd_std > 0 else np.nan

    max_dd = float(drawdown(returns).min())
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan

    active = returns[returns != 0]
    summary = {
        "total_return": total_return,
        "cagr": cagr,
        "volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "hit_rate": float((active > 0).mean()) if len(active) else np.nan,
    }
    if turnover is not None:
        summary["annual_turnover"] = float(turnover.sum() / n * periods_per_year)
    return summary
