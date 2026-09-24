"""Synthetic pair generator with known break dates — the "break lab".

Every scenario starts as a cointegrated pair
    A_t = beta * B_t + c + s_t,   s_t an Ornstein-Uhlenbeck (AR(1)) spread,
and optionally changes regime at ``break_at``. Because the truth is known,
detectors can be scored on detection rate, delay and false alarms.

Scenarios
---------
stable        relationship holds throughout                         (null)
temp_shock    spread jumps ~4 sigma, then mean-reverts  (opportunity, not a break)
drift_break   spread becomes a random walk with drift (permanent divergence)
death         company A collapses: steady decline, rising volatility
beta_shift    hedge ratio re-rates to a new level over ~60 days
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SCENARIOS = ["stable", "temp_shock", "drift_break", "death", "beta_shift"]
BREAK_SCENARIOS = {"drift_break", "death", "beta_shift"}


@dataclass
class SyntheticPair:
    prices: pd.DataFrame      # columns A, B
    scenario: str
    break_date: pd.Timestamp | None  # regime change (or shock) date


def generate_pair(
    scenario: str,
    n_days: int = 1500,
    break_at: int = 1000,
    seed: int | None = None,
    beta: float = 1.5,
    phi: float = 0.95,
    spread_sigma: float = 1.0,
) -> SyntheticPair:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}; choose from {SCENARIOS}")
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-01", periods=n_days)

    b = 50 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n_days)))
    eps = rng.normal(0, spread_sigma, n_days)
    stationary_sd = spread_sigma / np.sqrt(1 - phi**2)

    s = np.zeros(n_days)
    betas = np.full(n_days, beta)
    for t in range(1, n_days):
        s[t] = phi * s[t - 1] + eps[t]
        if scenario == "temp_shock" and t == break_at:
            s[t] -= 4.5 * stationary_sd * rng.choice([-1, 1])
    if scenario == "drift_break":
        s[break_at:] += np.cumsum(rng.normal(-0.04, 0.6, n_days - break_at)) * rng.choice([-1, 1])
    if scenario == "beta_shift":
        ramp = np.clip((np.arange(n_days) - break_at) / 60, 0, 1)
        betas = beta + ramp * rng.choice([-0.5, 0.5])

    a = betas * b + 20 + s

    if scenario == "death":
        k = np.arange(n_days) - break_at
        alive = k >= 0
        # Log-price decline ~-0.8%/day with volatility ramping up to 4%/day.
        vol = 0.01 + 0.03 * np.clip(k / 250, 0, 1)
        shocks = np.where(alive, rng.normal(-0.008, 1.0, n_days) * vol, 0.0)
        a = a * np.exp(np.cumsum(shocks))

    a = np.maximum(a, 0.01)
    prices = pd.DataFrame({"A": a, "B": b}, index=idx)
    has_break = scenario != "stable"
    return SyntheticPair(prices, scenario, idx[break_at] if has_break else None)
