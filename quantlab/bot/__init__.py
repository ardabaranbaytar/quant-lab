"""Statistical-arbitrage paper-trading bot.

The bot runs the multi-pair strategy of
:mod:`quantlab.strategies.pair_portfolio` one trading day at a time, against a
simulated broker, and persists everything so it can be resumed daily (cron /
Task Scheduler after the US close). Design: docs/paper_bot.md.

    prices up to today ──► StatArbBot.step(date) ──► orders ──► PaperBroker
          ▲                    │  (re)select pairs every quarter       │ filled at
          │                    │  z-score + BreakMonitor per pair      │ NEXT close
     DB / Yahoo                ▼                                       ▼
                         StepReport ──► store (bot_states, bot_equity,
                                               paper_fills, bot_events)

Decisions go through the same ``next_position`` state machine as the
backtest, and a parity test checks that replaying history through the bot
reproduces the backtest's positions exactly.
"""

from quantlab.bot.broker import Fill, Order, PaperBroker
from quantlab.bot.config import BotConfig
from quantlab.bot.core import StatArbBot, StepReport

__all__ = ["BotConfig", "Fill", "Order", "PaperBroker", "StatArbBot", "StepReport"]
