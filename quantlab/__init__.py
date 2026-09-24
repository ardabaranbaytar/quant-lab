"""quantlab: portfolio-level backtesting, factor research and statistical arbitrage."""

from quantlab.engine import BacktestResult, run_backtest
from quantlab.metrics import drawdown, performance_summary

__version__ = "0.1.0"

__all__ = ["BacktestResult", "drawdown", "performance_summary", "run_backtest"]
