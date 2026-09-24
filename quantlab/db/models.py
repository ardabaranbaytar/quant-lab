"""ORM models."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Double, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Price(Base):
    """Daily adjusted close, one row per (ticker, date)."""

    __tablename__ = "prices"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    close: Mapped[float] = mapped_column(Double, nullable=False)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(String(64), index=True)
    params: Mapped[dict] = mapped_column(JSON)
    tickers: Mapped[list] = mapped_column(JSON)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    cost_rate: Mapped[float] = mapped_column(Double)
    risk_free_rate: Mapped[float] = mapped_column(Double, default=0.0)
    benchmark_ticker: Mapped[str | None] = mapped_column(String(16), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    points: Mapped[list[BacktestPoint]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="BacktestPoint.date"
    )


class BacktestPoint(Base):
    """Daily equity curve of a run — kept in SQL so it can be queried/joined."""

    __tablename__ = "backtest_points"

    run_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    net_return: Mapped[float] = mapped_column(Double)
    equity: Mapped[float] = mapped_column(Double)
    drawdown: Mapped[float] = mapped_column(Double)

    run: Mapped[BacktestRun] = relationship(back_populates="points")


# ------------------------------------------------------------ paper bot


class BotState(Base):
    """Latest resumable state of a paper-trading bot (one row per bot)."""

    __tablename__ = "bot_states"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    config: Mapped[dict] = mapped_column(JSON)
    state: Mapped[dict] = mapped_column(JSON)
    last_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BotEquity(Base):
    """Daily mark-to-market of a bot, after that day's fills."""

    __tablename__ = "bot_equity"

    bot: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    equity: Mapped[float] = mapped_column(Double)
    cash: Mapped[float] = mapped_column(Double)
    gross_exposure: Mapped[float] = mapped_column(Double)  # fraction of equity
    open_pairs: Mapped[int] = mapped_column(Integer)


class PaperFill(Base):
    __tablename__ = "paper_fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot: Mapped[str] = mapped_column(String(64), index=True)
    order_date: Mapped[date] = mapped_column(Date)  # decision (signal) date
    fill_date: Mapped[date] = mapped_column(Date, index=True)
    ticker: Mapped[str] = mapped_column(String(16))
    qty: Mapped[float] = mapped_column(Double)  # signed shares
    price: Mapped[float] = mapped_column(Double)
    cost: Mapped[float] = mapped_column(Double)


class BotEvent(Base):
    """Pair-level decisions: entry, exit, stop, risk_exit, delisted, reselect..."""

    __tablename__ = "bot_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    pair: Mapped[str] = mapped_column(String(40))
    event: Mapped[str] = mapped_column(String(16))
    z: Mapped[float | None] = mapped_column(Double, nullable=True)
    detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
