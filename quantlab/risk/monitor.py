"""Combine detector scores into a per-day pair state.

NORMAL   trade as usual
WARNING  no new entries; existing trades may continue
BROKEN   exit now; the pair stays blocked until detectors are quiet for
         ``cooldown`` consecutive days

A detector "votes" when its score exceeds a threshold calibrated on stable
pairs (so each detector alone raises a false flag on ~1% of normal days).
Requiring several independent votes is what separates a real break from a
single noisy signal — and from a temporary shock, which trips z-score based
detectors but not the structural ones.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from quantlab.risk.detectors import DETECTORS, compute_detectors

NORMAL, WARNING, BROKEN = 0, 1, 2
STATE_NAMES = {NORMAL: "normal", WARNING: "warning", BROKEN: "broken"}

# Calibrated with `studies.break_lab --calibrate` (99th percentile of each
# detector on 200 synthetic stable pairs). Re-run after changing detectors.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "df_tstat": 0.021,
    "cusum": 31.04,
    "z_persistence": 0.35,
    "corr_drop": 0.184,
    "divergence": 3.97,
    "idio_vol_spike": 1.463,
    "trend_tstat": 1.843,
}


def calibrate(null_scores: Iterable[pd.DataFrame], quantile: float = 0.99) -> dict[str, float]:
    """Per-detector threshold = ``quantile`` of its scores on stable pairs."""
    stacked = pd.concat([s[DETECTORS] for s in null_scores]).dropna()
    return {d: float(np.quantile(stacked[d], quantile)) for d in DETECTORS}


@dataclass
class BreakMonitor:
    thresholds: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    warn_votes: int = 2
    break_votes: int = 3
    confirm_days: int = 8     # break votes needed on this many of the last
    confirm_window: int = 10  # ``confirm_window`` days (filters one-off shocks)
    cooldown: int = 60        # quiet days before a broken pair is re-enabled

    def votes(self, scores: pd.DataFrame) -> pd.DataFrame:
        flags = pd.DataFrame(
            {d: scores[d] > self.thresholds[d] for d in DETECTORS if d in self.thresholds}
        )
        return flags.fillna(False)

    def run(self, scores: pd.DataFrame) -> pd.DataFrame:
        flags = self.votes(scores)
        n_votes = flags.sum(axis=1).to_numpy()
        ready = scores[DETECTORS].notna().all(axis=1).to_numpy()
        heavy = (n_votes >= self.break_votes).astype(int)
        confirmed = pd.Series(heavy).rolling(self.confirm_window, min_periods=1).sum().to_numpy() >= self.confirm_days

        state = np.full(len(scores), NORMAL)
        broken, quiet = False, 0
        for t in range(len(scores)):
            if not ready[t]:
                state[t] = NORMAL
                continue
            if broken:
                quiet = quiet + 1 if n_votes[t] == 0 else 0
                if quiet >= self.cooldown:
                    broken, quiet = False, 0
            elif confirmed[t]:
                broken, quiet = True, 0
            if broken:
                state[t] = BROKEN
            elif n_votes[t] >= self.warn_votes:
                state[t] = WARNING
        out = flags.copy()
        out["votes"] = n_votes
        out["state"] = state
        out["ready"] = ready
        return out

    def evaluate_pair(self, pa: pd.Series, pb: pd.Series, **detector_kw) -> pd.DataFrame:
        scores = compute_detectors(pa, pb, **detector_kw)
        return scores.join(self.run(scores).drop(columns=DETECTORS))
