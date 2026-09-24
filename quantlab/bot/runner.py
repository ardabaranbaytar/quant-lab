"""Catch the bot up to the latest available close.

Idempotent: days already processed are skipped, so it is safe to schedule
daily or to re-run after a failure.
"""

from __future__ import annotations

from collections.abc import Callable, Collection

import pandas as pd
from sqlalchemy.orm import Session

from quantlab.bot import store
from quantlab.bot.config import BotConfig
from quantlab.bot.core import StatArbBot, StepReport

Eligible = Callable[[pd.Timestamp], Collection[str]]


def run_bot(
    session: Session,
    name: str,
    prices: pd.DataFrame,
    config: BotConfig | None = None,
    start=None,
    until=None,
    eligible: Eligible | None = None,
) -> list[StepReport]:
    """Step bot ``name`` through every unprocessed date in ``prices``.

    A new bot (``config`` required) starts at ``start`` — or at the last
    date in ``prices`` — so it never silently backfills years of history.
    """
    bot = store.load_bot(session, name)
    if bot is None:
        if config is None:
            raise ValueError(f"bot '{name}' does not exist; pass a config to create it")
        bot = StatArbBot(config)
        first = pd.Timestamp(start) if start is not None else prices.index[-1]
        dates = prices.index[prices.index >= first]
    else:
        dates = prices.index[prices.index > bot.last_date]
    if until is not None:
        dates = dates[dates <= pd.Timestamp(until)]

    reports = []
    for d in dates:
        report = bot.step(d, prices.loc[:d], None if eligible is None else eligible(d))
        store.record_step(session, name, bot, report)
        reports.append(report)
    return reports
