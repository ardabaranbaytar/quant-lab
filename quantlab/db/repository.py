"""Read/write helpers so the rest of the code never writes raw ORM queries."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from typing import Any, cast

import pandas as pd
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from quantlab.db.models import BacktestPoint, BacktestRun, Price
from quantlab.engine import BacktestResult
from quantlab.metrics import drawdown

# ----------------------------------------------------------------- prices


def save_prices(session: Session, prices: pd.DataFrame) -> int:
    """Replace stored prices for the tickers/date span in ``prices``."""
    long = cast(pd.Series, prices.stack(future_stack=True)).dropna().rename("close").reset_index()
    long.columns = ["date", "ticker", "close"]
    if long.empty:
        return 0
    long["date"] = pd.to_datetime(long["date"]).dt.date
    session.execute(
        delete(Price).where(
            Price.ticker.in_(prices.columns.tolist()),
            Price.date >= long["date"].min(),
            Price.date <= long["date"].max(),
        )
    )
    records = cast(list[dict[str, Any]], long.to_dict("records"))
    session.execute(insert(Price), records)
    return len(long)


def load_prices(session: Session, tickers: Iterable[str], start, end) -> pd.DataFrame:
    rows = session.execute(
        select(Price.date, Price.ticker, Price.close).where(
            Price.ticker.in_(list(tickers)), Price.date >= start, Price.date <= end
        )
    ).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "ticker", "close"])
    wide = df.pivot(index="date", columns="ticker", values="close").sort_index()
    wide.index = pd.DatetimeIndex(wide.index)
    wide.columns.name = None
    return wide


def price_coverage(session: Session, tickers: Iterable[str]) -> dict[str, tuple]:
    rows = session.execute(
        select(Price.ticker, func.min(Price.date), func.max(Price.date))
        .where(Price.ticker.in_(list(tickers)))
        .group_by(Price.ticker)
    ).all()
    return {t: (lo, hi) for t, lo, hi in rows}


def get_prices(
    session: Session,
    tickers: Iterable[str],
    start: str,
    end: str,
    fetch: Callable[[list[str], str, str], pd.DataFrame] | None = None,
    allow_missing: bool = False,
) -> pd.DataFrame:
    """Serve prices from the DB, downloading tickers whose history is missing.

    ``fetch`` defaults to Yahoo Finance; tests inject a fake. With
    ``allow_missing`` unknown tickers are dropped instead of raising.
    """
    tickers = sorted({t.upper() for t in tickers})
    start_d, end_d = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    coverage = price_coverage(session, tickers)
    tolerance = pd.Timedelta(days=5)  # weekends/holidays at the edges
    missing = [
        t
        for t in tickers
        if t not in coverage
        or pd.Timestamp(coverage[t][0]) - tolerance > pd.Timestamp(start_d)
        or pd.Timestamp(coverage[t][1]) + tolerance < pd.Timestamp(end_d)
    ]
    if missing:
        try:
            save_prices(session, (fetch or _fetch_yahoo)(missing, start, end))
            session.flush()
        except ValueError:
            if not allow_missing:
                raise

    prices = load_prices(session, tickers, start_d, end_d)
    absent = [t for t in tickers if t not in prices.columns]
    if absent and not allow_missing:
        raise ValueError(f"No price data for: {', '.join(absent)}")
    return prices[[t for t in tickers if t in prices.columns]]


def refresh_prices(
    session: Session,
    tickers: Iterable[str],
    start: str,
    end: str,
    fetch: Callable[[list[str], str, str], pd.DataFrame] | None = None,
) -> int:
    """Re-download closes in [start, end] and replace what is stored.

    ``get_prices`` treats a few days at the edges as covered (weekends,
    holidays): right for research, but it would starve a daily job of new
    closes. This also overwrites intraday bars stored by an earlier run while
    the market was open. Rows after ``end`` are never stored.
    """
    tickers = sorted({t.upper() for t in tickers})
    try:
        fresh = (fetch or _fetch_yahoo)(tickers, start, str((pd.Timestamp(end) + pd.Timedelta(days=1)).date()))
    except ValueError:  # no rows at all in the window (e.g. a long holiday)
        return 0
    n = save_prices(session, fresh.loc[: pd.Timestamp(end)])
    session.flush()
    return n


def _fetch_yahoo(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    from quantlab.data import load_prices as fetch_yahoo

    return fetch_yahoo(tickers, start, end, cache_dir=None)


# ------------------------------------------------------------- backtests


def _clean(d: dict) -> dict:
    """JSON columns can't hold NaN/inf."""
    return {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in d.items()}


def save_backtest(
    session: Session,
    *,
    strategy: str,
    params: dict,
    tickers: list[str],
    cost_rate: float,
    result: BacktestResult,
    metrics: dict,
    risk_free_rate: float = 0.0,
    benchmark: str | None = None,
) -> BacktestRun:
    rets = result.net_returns
    run = BacktestRun(
        strategy=strategy,
        params=params,
        tickers=tickers,
        start_date=rets.index[0].date(),
        end_date=rets.index[-1].date(),
        cost_rate=cost_rate,
        risk_free_rate=risk_free_rate,
        benchmark_ticker=benchmark,
        metrics=_clean(metrics),
    )
    dd = drawdown(rets)
    equity = result.equity
    run.points = [
        BacktestPoint(date=d.date(), net_return=float(r), equity=float(e), drawdown=float(x))
        for d, r, e, x in zip(rets.index, rets, equity, dd)
    ]
    session.add(run)
    session.flush()
    return run


def list_backtests(session: Session, limit: int = 50) -> list[BacktestRun]:
    return list(
        session.scalars(select(BacktestRun).order_by(BacktestRun.id.desc()).limit(limit))
    )


def get_backtest(session: Session, run_id: int) -> BacktestRun | None:
    return session.get(BacktestRun, run_id)
