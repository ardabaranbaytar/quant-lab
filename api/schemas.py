"""Request/response models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
        return list(dict.fromkeys(t.strip().upper() for t in v if t.strip()))


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
