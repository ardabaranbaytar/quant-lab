"""Request/response models."""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# The API is public, so request values are bounded here rather than trusted downstream.
# Yahoo-style symbols: letters, digits and . - = ^  (BRK-B, ^GSPC, EURUSD=X); 16 = column width.
_TICKER_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=]{0,15}$")
MAX_SPAN_DAYS = 366 * 30
MAX_PARAMS = 20
MAX_PARAM_ABS = 10_000  # windows/thresholds: ~27 years of daily bars is far beyond any real use
MAX_PARAM_TEXT = 16


def _ticker(value: str) -> str:
    symbol = value.strip().upper()
    if not _TICKER_RE.fullmatch(symbol):
        raise ValueError(f"invalid ticker symbol {symbol[:20]!r}")
    return symbol


def _check_span(start: date, end: date) -> None:
    if (end - start).days > MAX_SPAN_DAYS:
        raise ValueError("date range is longer than 30 years")


class TickerCheckRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=50)

    @field_validator("symbols")
    @classmethod
    def normalise_symbols(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(_ticker(s) for s in v))


class TickerCheckResponse(BaseModel):
    # symbol -> True (has price history), False (Yahoo does not know it), None (could not tell)
    results: dict[str, bool | None]


class AdminSession(BaseModel):
    enabled: bool  # a delete key is configured on the server
    authorized: bool  # the key sent with this request is the right one


class DeleteBacktestsRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=500)
    delete_all: bool = False

    @model_validator(mode="after")
    def need_a_target(self) -> DeleteBacktestsRequest:
        if not self.delete_all and not self.ids:
            raise ValueError("give ids or set delete_all")
        return self


class DeleteResult(BaseModel):
    deleted: int


class StrategyInfo(BaseModel):
    name: str
    description: str
    params: dict[str, Any]  # param name -> default value
    min_tickers: int


class BacktestRequest(BaseModel):
    strategy: str
    tickers: list[str] = Field(min_length=1, max_length=100)
    start: date
    end: date
    params: dict[str, Any] = {}
    cost_rate: float = Field(0.001, ge=0, le=0.05)
    risk_free_rate: float = Field(0.0, ge=0, le=0.2)
    benchmark: str | None = "SPY"

    @field_validator("tickers")
    @classmethod
    def normalise_tickers(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(_ticker(t) for t in v if t.strip()))

    @field_validator("benchmark")
    @classmethod
    def normalise_benchmark(cls, v: str | None) -> str | None:
        return _ticker(v) if v and v.strip() else None

    @field_validator("params")
    @classmethod
    def scalar_params(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > MAX_PARAMS:
            raise ValueError(f"at most {MAX_PARAMS} params")
        for name, value in v.items():
            if len(name) > 32:
                raise ValueError("param name is too long")
            if value is None or isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                if not math.isfinite(value) or abs(value) > MAX_PARAM_ABS:
                    raise ValueError(f"param {name!r} is out of range")
            elif isinstance(value, str):
                if len(value) > MAX_PARAM_TEXT:
                    raise ValueError(f"param {name!r} is too long")
            else:
                # ValueError on purpose: pydantic turns it into a 422, a TypeError would be a 500.
                raise ValueError(f"param {name!r} must be a number, text or null")  # noqa: TRY004
        return v

    @model_validator(mode="after")
    def limit_span(self) -> BacktestRequest:
        _check_span(self.start, self.end)
        return self


class Point(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    equity: float
    drawdown: float


class BacktestSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy: str
    params: dict[str, Any]
    tickers: list[str]
    start_date: date
    end_date: date
    cost_rate: float
    metrics: dict[str, float | None]
    created_at: datetime | None = None


class BacktestDetail(BacktestSummary):
    points: list[Point]
    benchmark: list[Point] | None = None
    benchmark_metrics: dict[str, float | None] | None = None


class PairScanRequest(BaseModel):
    tickers: list[str] = Field(min_length=2, max_length=40)
    start: date
    end: date

    @field_validator("tickers")
    @classmethod
    def normalise_tickers(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(_ticker(t) for t in v))

    @model_validator(mode="after")
    def limit_span(self) -> PairScanRequest:
        _check_span(self.start, self.end)
        return self


class PairScanRow(BaseModel):
    pair: str
    asset_a: str
    asset_b: str
    correlation: float
    coint_pvalue: float
    hedge_ratio: float
    half_life: float | None


class PairScanResponse(BaseModel):
    pairs: list[PairScanRow]
    skipped: list[str]  # tickers with no price data


# ------------------------------------------------------------ paper bot


class BotSummary(BaseModel):
    name: str
    last_date: date | None
    equity: float | None
    open_pairs: int | None
    updated_at: datetime | None = None


class BotEquityPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    equity: float
    cash: float
    gross_exposure: float
    open_pairs: int


class BotFill(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_date: date
    fill_date: date
    ticker: str
    qty: float
    price: float
    cost: float


class BotEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    pair: str
    event: str
    z: float | None
    detail: str | None


class BotOpenPair(BaseModel):
    pair: str
    pos: int
    shares_a: float
    shares_b: float
    entry_date: str | None


class BotPendingOrder(BaseModel):
    ticker: str
    qty: float
    order_date: date


class BotStatus(BaseModel):
    name: str
    last_date: date | None
    updated_at: datetime | None
    cash: float
    positions: dict[str, float]
    pending_orders: list[BotPendingOrder]  # decided on last_date, fill at the next close
    days_in_period: int                    # trading days since the last pair re-selection
    pairs: list[str]
    open_pairs: list[BotOpenPair]
    config: dict[str, Any]
