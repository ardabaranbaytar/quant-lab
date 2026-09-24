"""The bot: one ``step`` per trading day, after the close.

Each step
1. fills yesterday's orders at today's close (:class:`PaperBroker`),
2. re-selects pairs every ``reselect_every`` days (all pair trades are closed
   first, exactly like a new period of the backtest),
3. updates every pair through the shared ``next_position`` state machine,
   consulting the :class:`BreakMonitor` only when it can change a decision,
4. sizes new trades in shares (``1/top_k`` of current equity, legs 1 : beta),
   holds those shares until the trade closes, and submits the net orders.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import asdict, dataclass, field
from typing import Any, cast

import numpy as np
import pandas as pd

from quantlab.bot.broker import Fill, Order, PaperBroker
from quantlab.bot.config import BotConfig
from quantlab.risk.monitor import NORMAL, BreakMonitor
from quantlab.strategies.pair_portfolio import (
    SelectedPair,
    leg_weights,
    next_position,
    pair_zscore,
    pairs_from_frame,
    select_pairs,
)


@dataclass
class PairBook:
    pos: int = 0
    armed: bool = True
    shares_a: float = 0.0
    shares_b: float = 0.0
    entry_date: str | None = None


@dataclass
class StepReport:
    date: pd.Timestamp
    equity: float
    cash: float
    gross_exposure: float
    open_pairs: int
    fills: list[Fill] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    target_weights: dict[str, float] = field(default_factory=dict)  # model book, NAV weights


def _key(p: SelectedPair) -> str:
    return f"{p.a}/{p.b}"


class StatArbBot:
    def __init__(self, config: BotConfig, state: dict[str, Any] | None = None):
        self.config = config
        self.monitor: BreakMonitor | None = None
        if config.break_monitor:
            self.monitor = (BreakMonitor(thresholds=dict(config.monitor_thresholds),
                                         break_votes=config.break_votes)
                            if config.monitor_thresholds else BreakMonitor(break_votes=config.break_votes))
        if state is None:
            self.broker = PaperBroker(cash=config.capital, cost_rate=config.cost_rate)
            self.last_date: pd.Timestamp | None = None
            self.days_in_period = config.reselect_every  # first selection is due
            self.pairs: list[SelectedPair] = []
            self.books: dict[str, PairBook] = {}
        else:
            self.broker = PaperBroker.from_dict(state["broker"])
            self.last_date = pd.Timestamp(state["last_date"]) if state["last_date"] else None
            self.days_in_period = int(state["days_in_period"])
            self.pairs = [SelectedPair(**p) for p in state["pairs"]]
            self.books = {k: PairBook(**b) for k, b in state["books"].items()}

    # ------------------------------------------------------------ state

    def state_dict(self) -> dict[str, Any]:
        return {
            "last_date": None if self.last_date is None else str(self.last_date.date()),
            "days_in_period": self.days_in_period,
            "pairs": [asdict(p) for p in self.pairs],
            "books": {k: asdict(b) for k, b in self.books.items()},
            "broker": self.broker.to_dict(),
        }

    # ------------------------------------------------------------- step

    def _reselect(self, history: pd.DataFrame, eligible: Collection[str] | None) -> pd.DataFrame:
        cfg = self.config
        window = cast(pd.DataFrame, np.log(history.iloc[-cfg.formation_days:]))
        tickers = [t for t in window.columns[window.notna().all()]
                   if t in cfg.groups and (eligible is None or t in eligible)]
        return select_pairs(window[tickers], cfg.groups, cfg.max_pvalue, cfg.half_life_range,
                            cfg.top_k, cfg.max_pairs_per_stock, companies=cfg.companies)

    def _risk_state(self, history: pd.DataFrame, p: SelectedPair) -> int:
        if self.monitor is None:
            return NORMAL
        # Detectors are causal, so evaluating on history up to today gives
        # the same state the backtest sees on that day.
        states = self.monitor.evaluate_pair(history[p.a], history[p.b])["state"]
        return int(states.iloc[-1])

    def step(
        self, date, history: pd.DataFrame, eligible: Collection[str] | None = None
    ) -> StepReport:
        """Advance one trading day. ``history`` holds closes up to and including
        ``date`` (later rows are ignored); ``eligible`` restricts which tickers
        may be selected at a re-selection (point-in-time index membership)."""
        cfg = self.config
        date = pd.Timestamp(date)
        if self.last_date is not None and date <= self.last_date:
            raise ValueError(f"{date.date()} already processed (last: {self.last_date.date()})")
        history = history.loc[:date]
        if history.empty or history.index[-1] != date:
            raise ValueError(f"no prices for {date.date()}")
        iso = str(date.date())
        today = history.iloc[-1]
        # Delisted names keep their last close, so their legs can still be closed.
        marks = {str(t): float(v) for t, v in history.ffill().iloc[-1].items()}

        fills = self.broker.fill_pending(iso, marks)
        equity = self.broker.equity(marks)
        events: list[dict[str, Any]] = []

        # A selection that finds no pairs is not retried until the next period
        # (same as the backtest), so an empty book is a decision, not a gap.
        if self.days_in_period >= cfg.reselect_every and len(history) >= cfg.formation_days:
            for key, book in self.books.items():
                if book.pos:
                    events.append({"pair": key, "event": "period_close", "z": None})
            self.pairs = pairs_from_frame(self._reselect(history, eligible))
            self.books = {_key(p): PairBook() for p in self.pairs}
            self.days_in_period = 0
            events.append({"pair": "*", "event": "reselect", "z": None,
                           "detail": ", ".join(self.books) or "no pairs"})

        target: dict[str, float] = {}
        model_weights: dict[str, float] = {}
        for p in self.pairs:
            book = self.books[_key(p)]
            z = pair_zscore(p, today[p.a], today[p.b])
            could_change = book.pos != 0 or (book.armed and abs(z) > cfg.entry_z)
            state = self._risk_state(history, p) if could_change and np.isfinite(z) else NORMAL
            pos, armed, event = next_position(book.pos, book.armed, z, state,
                                              cfg.entry_z, cfg.exit_z, cfg.stop_z)
            book.armed = armed
            if event == "entry":
                wa, wb = leg_weights(pos, p.beta, cfg.top_k)
                book.shares_a = wa * equity / today[p.a]
                book.shares_b = wb * equity / today[p.b]
                book.entry_date = iso
            elif pos == 0:
                book.shares_a = book.shares_b = 0.0
                book.entry_date = None
            book.pos = pos
            if event:
                events.append({"pair": _key(p), "event": event, "z": None if np.isnan(z) else z})
            if pos:
                wa, wb = leg_weights(pos, p.beta, cfg.top_k)
                model_weights[p.a] = model_weights.get(p.a, 0.0) + wa
                model_weights[p.b] = model_weights.get(p.b, 0.0) + wb
                target[p.a] = target.get(p.a, 0.0) + book.shares_a
                target[p.b] = target.get(p.b, 0.0) + book.shares_b

        orders = []
        for t in sorted(set(target) | set(self.broker.positions)):
            qty = target.get(t, 0.0) - self.broker.positions.get(t, 0.0)
            if abs(qty * marks[t]) >= cfg.min_order_value:
                orders.append(Order(t, qty, iso))
        self.broker.submit(orders)

        self.days_in_period += 1
        self.last_date = date
        return StepReport(
            date=date,
            equity=equity,
            cash=self.broker.cash,
            gross_exposure=self.broker.gross_value(marks) / equity if equity else 0.0,
            open_pairs=sum(1 for b in self.books.values() if b.pos),
            fills=fills,
            orders=orders,
            events=events,
            target_weights=model_weights,
        )
