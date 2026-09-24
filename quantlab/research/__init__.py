"""Research tools: factor analysis and pair selection."""

from quantlab.research.factors import (
    forward_returns,
    information_coefficient,
    momentum,
    quantile_returns,
    volatility,
)
from quantlab.research.pairs import scan_pairs

__all__ = [
    "forward_returns",
    "information_coefficient",
    "momentum",
    "quantile_returns",
    "scan_pairs",
    "volatility",
]
