"""Risk layer for statistical arbitrage: detect when a pair's relationship
breaks for good (divergence, company distress, re-rating) as opposed to a
temporary dislocation that is a trading opportunity."""

from quantlab.risk.detectors import compute_detectors
from quantlab.risk.monitor import BROKEN, NORMAL, WARNING, BreakMonitor

__all__ = ["BROKEN", "NORMAL", "WARNING", "BreakMonitor", "compute_detectors"]
