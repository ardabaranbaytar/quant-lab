"""Strategies: functions mapping prices (dates x tickers) -> target weights.

Every strategy has the signature ``fn(prices, **params) -> DataFrame`` and only
uses information available at the close of each day, so its output can go
straight into :func:`quantlab.engine.run_backtest`.
"""

from quantlab.strategies.cross_sectional import cross_sectional_momentum
from quantlab.strategies.pairs import pairs_trading
from quantlab.strategies.single_asset import buy_and_hold, mean_reversion, ts_momentum

STRATEGIES = {
    "buy_and_hold": buy_and_hold,
    "ts_momentum": ts_momentum,
    "mean_reversion": mean_reversion,
    "cross_sectional_momentum": cross_sectional_momentum,
    "pairs_trading": pairs_trading,
}

__all__ = [
    "STRATEGIES",
    "buy_and_hold",
    "cross_sectional_momentum",
    "mean_reversion",
    "pairs_trading",
    "ts_momentum",
]
