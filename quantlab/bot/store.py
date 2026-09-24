"""Persist bot state and history (MySQL in production, SQLite in tests)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from quantlab.bot.config import BotConfig
from quantlab.bot.core import StatArbBot, StepReport
from quantlab.db.models import BotEquity, BotEvent, BotState, PaperFill


def load_bot(session: Session, name: str) -> StatArbBot | None:
    row = session.get(BotState, name)
    if row is None:
        return None
    return StatArbBot(BotConfig.from_dict(row.config), row.state)


def record_step(session: Session, name: str, bot: StatArbBot, report: StepReport) -> None:
    """Write one step's results and the bot's new state (same transaction)."""
    day = report.date.date()
    session.add(BotEquity(bot=name, date=day, equity=report.equity, cash=report.cash,
                          gross_exposure=report.gross_exposure, open_pairs=report.open_pairs))
    session.add_all(
        PaperFill(bot=name, order_date=pd.Timestamp(f.order_date).date(), fill_date=day,
                  ticker=f.ticker, qty=f.qty, price=f.price, cost=f.cost)
        for f in report.fills
    )
    session.add_all(
        BotEvent(bot=name, date=day, pair=e["pair"], event=e["event"], z=e.get("z"),
                 detail=str(e["detail"])[:255] if e.get("detail") else None)
        for e in report.events
    )
    row = session.get(BotState, name)
    if row is None:
        row = BotState(name=name, config=bot.config.to_dict())
        session.add(row)
    row.state = bot.state_dict()
    row.last_date = day
    # Explicit naive UTC: MySQL NOW() would use the server's local time zone.
    row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.flush()


def list_bots(session: Session) -> list[BotState]:
    return list(session.scalars(select(BotState).order_by(BotState.name)))


def equity_curve(session: Session, name: str) -> list[BotEquity]:
    return list(session.scalars(
        select(BotEquity).where(BotEquity.bot == name).order_by(BotEquity.date)
    ))


def fills(session: Session, name: str, limit: int = 200) -> list[PaperFill]:
    return list(session.scalars(
        select(PaperFill).where(PaperFill.bot == name).order_by(PaperFill.id.desc()).limit(limit)
    ))


def events(session: Session, name: str, limit: int = 200) -> list[BotEvent]:
    return list(session.scalars(
        select(BotEvent).where(BotEvent.bot == name).order_by(BotEvent.id.desc()).limit(limit)
    ))


def status(session: Session, name: str) -> dict[str, Any] | None:
    """Current book: cash, positions, pending orders, open pair trades and the
    settings the bot runs with (ticker maps summarised, not dumped)."""
    row = session.get(BotState, name)
    if row is None:
        return None
    s = row.state
    config = {k: v for k, v in row.config.items() if k not in ("groups", "companies")}
    config["universe_size"] = len(row.config.get("groups") or {})
    return {
        "name": name,
        "last_date": row.last_date,
        "updated_at": row.updated_at,
        "cash": s["broker"]["cash"],
        "positions": s["broker"]["positions"],
        "pending_orders": s["broker"]["pending"],
        "days_in_period": s["days_in_period"],
        "pairs": [f"{p['a']}/{p['b']}" for p in s["pairs"]],
        "open_pairs": [{"pair": k, **b} for k, b in s["books"].items() if b["pos"]],
        "config": config,
    }
