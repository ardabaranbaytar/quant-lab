"""Simulated broker for paper trading.

Orders decided on day t's close are filled at day t+1's close (market-on-close
the next session): the bot runs after the close, so it can never trade at the
price it used to decide. Costs are ``cost_rate`` x traded notional. Fractional
shares are allowed (as with most retail paper-trading APIs).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Order:
    ticker: str
    qty: float          # signed shares
    order_date: str     # ISO date of the decision


@dataclass(frozen=True)
class Fill:
    ticker: str
    qty: float
    price: float
    cost: float
    order_date: str
    fill_date: str


@dataclass
class PaperBroker:
    cash: float
    cost_rate: float = 0.001
    positions: dict[str, float] = field(default_factory=dict)
    pending: list[Order] = field(default_factory=list)

    def submit(self, orders: list[Order]) -> None:
        self.pending.extend(orders)

    def fill_pending(self, fill_date: str, prices: Mapping[str, float]) -> list[Fill]:
        """Fill every pending order at ``prices`` (the fill session's close).

        A ticker with no price at all is left pending; the caller passes the
        last known close for delisted names so their legs can be closed out.
        """
        fills, still_pending = [], []
        for o in self.pending:
            px = prices.get(o.ticker, math.nan)
            if not math.isfinite(px):
                still_pending.append(o)
                continue
            cost = abs(o.qty * px) * self.cost_rate
            self.cash -= o.qty * px + cost
            qty = self.positions.get(o.ticker, 0.0) + o.qty
            if abs(qty) < 1e-9:
                self.positions.pop(o.ticker, None)
            else:
                self.positions[o.ticker] = qty
            fills.append(Fill(o.ticker, o.qty, px, cost, o.order_date, fill_date))
        self.pending = still_pending
        return fills

    def market_value(self, prices: Mapping[str, float]) -> float:
        return sum(q * prices[t] for t, q in self.positions.items())

    def gross_value(self, prices: Mapping[str, float]) -> float:
        return sum(abs(q * prices[t]) for t, q in self.positions.items())

    def equity(self, prices: Mapping[str, float]) -> float:
        return self.cash + self.market_value(prices)

    def to_dict(self) -> dict[str, Any]:
        return {"cash": self.cash, "cost_rate": self.cost_rate, "positions": dict(self.positions),
                "pending": [asdict(o) for o in self.pending]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PaperBroker:
        return cls(cash=float(d["cash"]), cost_rate=float(d["cost_rate"]),
                   positions={t: float(q) for t, q in d["positions"].items()},
                   pending=[Order(**o) for o in d["pending"]])
