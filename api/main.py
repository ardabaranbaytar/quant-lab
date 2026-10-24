"""FastAPI service: run backtests, browse saved runs, scan pairs, follow paper bots.

Run locally:  uvicorn api.main:app --reload
"""

from __future__ import annotations

import hmac
import inspect
import logging
import math
import os
import threading
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from api.schemas import (
    AdminSession,
    BacktestDetail,
    BacktestRequest,
    BacktestSummary,
    BotEquityPoint,
    BotEventOut,
    BotFill,
    BotStatus,
    BotSummary,
    DeleteBacktestsRequest,
    DeleteResult,
    PairScanRequest,
    PairScanResponse,
    Point,
    SecurityHit,
    StrategyInfo,
    TickerCheckRequest,
    TickerCheckResponse,
)
from quantlab import securities
from quantlab.bot import store as bot_store
from quantlab.db import init_db, session_scope
from quantlab.db import repository as repo
from quantlab.engine import ffill_within_life, run_backtest
from quantlab.metrics import drawdown, performance_summary
from quantlab.research.pairs import scan_pairs
from quantlab.strategies import STRATEGIES

log = logging.getLogger(__name__)

MIN_TICKERS = {"pairs_trading": 2}
INTERNAL_PARAMS = {"universe", "break_monitor"}  # set server-side, not user-editable

# POST /backtests is anonymous and stores every run (one row per day of the curve), so only
# the newest runs are kept. 0 disables pruning.
MAX_STORED_RUNS = int(os.getenv("QUANTLAB_MAX_STORED_RUNS", "500"))

# Deleting history is for the owner only: a key in the server's .env (QUANTLAB_ADMIN_TOKEN) that the
# History page sends as X-Admin-Token. No key, or one shorter than this, switches the feature off.
MIN_ADMIN_KEY_LENGTH = 24


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="quant-lab API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # Production is same-origin behind Caddy; this only matters for other front ends.
    allow_origins=os.getenv("QUANTLAB_CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

# Backtests and pair scans download prices and burn CPU. On a small public
# server a couple at a time is the limit; extra requests get 429, not a queue.
_HEAVY_JOBS = threading.BoundedSemaphore(int(os.getenv("QUANTLAB_MAX_HEAVY_JOBS", "2")))


def heavy_slot() -> Iterator[None]:
    if not _HEAVY_JOBS.acquire(blocking=False):
        raise HTTPException(429, "Server busy: too many backtests running. Try again in a moment.")
    try:
        yield
    finally:
        _HEAVY_JOBS.release()


# "Does this symbol exist?" is asked while the visitor types, and anything we have not stored yet
# costs a Yahoo lookup. So: its own small concurrency cap (busy means "could not tell", never an
# error), and answers are remembered for a while in a bounded cache, so a retyped typo is free.
_CHECK_JOBS = threading.BoundedSemaphore(int(os.getenv("QUANTLAB_MAX_CHECK_JOBS", "2")))
_CHECK_TTL_FOUND = 24 * 3600.0
_CHECK_TTL_MISSING = 3600.0
_CHECK_CACHE_MAX = 2000
_CHECKED: dict[str, tuple[bool, float]] = {}  # symbol -> (exists, valid until)


def _remember_symbols(found: set[str], asked: list[str]) -> None:
    now = time.monotonic()
    for sym in asked:
        exists = sym in found
        _CHECKED[sym] = (exists, now + (_CHECK_TTL_FOUND if exists else _CHECK_TTL_MISSING))
    while len(_CHECKED) > _CHECK_CACHE_MAX:
        _CHECKED.pop(next(iter(_CHECKED)))  # oldest first: dicts keep insertion order


def _lookup_symbols(symbols: list[str]) -> dict[str, bool | None]:
    """Ask Yahoo about symbols we cannot answer ourselves; None where it did not answer."""
    from quantlab.data import symbols_with_history

    if not _CHECK_JOBS.acquire(blocking=False):
        return dict.fromkeys(symbols)
    try:
        found = symbols_with_history(symbols)
    except Exception:  # Yahoo down, throttled or changed: "could not tell" must not block typing
        log.warning("ticker check failed for %s", symbols, exc_info=True)
        return dict.fromkeys(symbols)
    finally:
        _CHECK_JOBS.release()
    _remember_symbols(found, symbols)
    return {s: s in found for s in symbols}


# The picker searches our own list first. Yahoo is only asked about what that list lacks (other
# exchanges, small caps), through the same cap as the existence check, and answers are remembered.
_YAHOO_SEARCH_MIN_CHARS = 3
_SEARCHED: dict[str, tuple[list[SecurityHit], float]] = {}  # folded query -> (hits, valid until)
_SEARCH_TTL = 3600.0
_SEARCH_CACHE_MAX = 500


def _yahoo_hits(query: str, limit: int) -> list[SecurityHit]:
    from quantlab.data import search_symbols

    key = securities.fold(query)
    cached = _SEARCHED.get(key)
    if cached and cached[1] > time.monotonic():
        return cached[0][:limit]
    if not _CHECK_JOBS.acquire(blocking=False):
        return []
    try:
        found = search_symbols(query, limit=6)
    except Exception:  # Yahoo down, throttled, or no Search in this yfinance: the local list still answers
        log.warning("symbol search failed for %r", query, exc_info=True)
        return []
    finally:
        _CHECK_JOBS.release()
    hits = [SecurityHit(symbol=s, name=n, kind=k, group=g) for s, n, k, g in found]
    _SEARCHED[key] = (hits, time.monotonic() + _SEARCH_TTL)
    while len(_SEARCHED) > _SEARCH_CACHE_MAX:
        _SEARCHED.pop(next(iter(_SEARCHED)))
    return hits[:limit]


def _strategy_params(fn) -> dict:
    sig = inspect.signature(fn)
    return {
        name: p.default
        for name, p in list(sig.parameters.items())[1:]  # skip `prices`
        if p.default is not inspect.Parameter.empty and name not in INTERNAL_PARAMS
    }


def _finite(d: dict) -> dict:
    return {k: (v if isinstance(v, (int, float)) and math.isfinite(v) else None) for k, v in d.items()}


def _curve(returns: pd.Series) -> list[Point]:
    equity = (1 + returns).cumprod()
    dd = drawdown(returns)
    return [
        Point(date=d.date(), equity=float(e), drawdown=float(x))
        for d, e, x in zip(returns.index, equity, dd)
    ]


def _with_benchmark(session: Session, run) -> BacktestDetail:
    """Attach the benchmark's buy-and-hold curve over the run's exact dates."""
    detail = BacktestDetail.model_validate(run)
    if not run.benchmark_ticker or not run.points:
        return detail
    px = repo.load_prices(session, [run.benchmark_ticker], run.start_date, run.end_date)
    if px.empty:
        return detail
    dates = pd.DatetimeIndex([p.date for p in run.points])
    bench = px[run.benchmark_ticker].reindex(dates).ffill().pct_change().fillna(0.0)
    detail.benchmark = _curve(bench)
    detail.benchmark_metrics = _finite(performance_summary(bench, run.risk_free_rate or 0.0))
    return detail


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/tickers/check", response_model=TickerCheckResponse)
def check_tickers(req: TickerCheckRequest, session: SessionDep):
    stored = set(repo.price_coverage(session, req.symbols))
    now = time.monotonic()
    results: dict[str, bool | None] = {}
    unknown: list[str] = []
    for sym in req.symbols:
        cached = _CHECKED.get(sym)
        if sym in stored:
            results[sym] = True
        elif cached and cached[1] > now:
            results[sym] = cached[0]
        else:
            unknown.append(sym)
    if unknown:
        results.update(_lookup_symbols(unknown))
    return TickerCheckResponse(results={s: results[s] for s in req.symbols})


@app.get("/tickers/search", response_model=list[SecurityHit])
def search_tickers(
    q: Annotated[str, Query(min_length=1, max_length=40)],
    limit: Annotated[int, Query(ge=1, le=15)] = 8,
):
    hits = [
        SecurityHit(symbol=s.symbol, name=s.name, kind=s.kind, group=s.group)
        for s in securities.search(q, limit)
    ]
    query = q.strip()
    if len(hits) < limit and len(query) >= _YAHOO_SEARCH_MIN_CHARS:
        have = {h.symbol for h in hits}
        hits += [h for h in _yahoo_hits(query, limit) if h.symbol not in have][: limit - len(hits)]
    return hits


@app.get("/strategies", response_model=list[StrategyInfo])
def list_strategies() -> list[StrategyInfo]:
    return [
        StrategyInfo(
            name=name,
            description=(inspect.getdoc(fn) or "").split("\n")[0].replace("``", ""),
            params=_strategy_params(fn),
            min_tickers=MIN_TICKERS.get(name, 1),
        )
        for name, fn in STRATEGIES.items()
    ]


@app.post("/backtests", response_model=BacktestDetail, status_code=201,
          dependencies=[Depends(heavy_slot)])
def create_backtest(req: BacktestRequest, session: SessionDep):
    fn = STRATEGIES.get(req.strategy)
    if fn is None:
        raise HTTPException(404, f"Unknown strategy '{req.strategy}'")
    if len(req.tickers) < MIN_TICKERS.get(req.strategy, 1):
        raise HTTPException(422, f"{req.strategy} needs at least {MIN_TICKERS[req.strategy]} tickers")
    if req.start >= req.end:
        raise HTTPException(422, "start must be before end")
    unknown = set(req.params) - set(_strategy_params(fn))
    if unknown:
        raise HTTPException(422, f"Unknown params: {sorted(unknown)}")

    wanted = req.tickers + ([req.benchmark] if req.benchmark else [])
    try:
        all_prices = repo.get_prices(session, wanted, str(req.start), str(req.end))
        prices = ffill_within_life(all_prices[req.tickers])
        result = run_backtest(prices, fn(prices, **req.params), req.cost_rate)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc

    metrics = performance_summary(result.net_returns, req.risk_free_rate, result.turnover)
    run = repo.save_backtest(
        session,
        strategy=req.strategy,
        params={**_strategy_params(fn), **req.params},
        tickers=req.tickers,
        cost_rate=req.cost_rate,
        result=result,
        metrics=metrics,
        risk_free_rate=req.risk_free_rate,
        benchmark=req.benchmark,
    )
    repo.prune_backtests(session, MAX_STORED_RUNS)
    return _with_benchmark(session, run)


def _admin_key() -> str | None:
    key = os.getenv("QUANTLAB_ADMIN_TOKEN", "")
    return key if len(key) >= MIN_ADMIN_KEY_LENGTH else None


def _is_admin(sent: str | None) -> bool:
    key = _admin_key()
    return bool(key and sent and hmac.compare_digest(sent.encode(), key.encode()))


AdminKeyHeader = Annotated[str | None, Header(alias="X-Admin-Token")]


def require_admin(sent: AdminKeyHeader = None) -> None:
    if _admin_key() is None:
        raise HTTPException(404, "Not found")
    if not _is_admin(sent):
        raise HTTPException(401, "Invalid admin key")


@app.get("/admin/session", response_model=AdminSession)
def admin_session(sent: AdminKeyHeader = None):
    return AdminSession(enabled=_admin_key() is not None, authorized=_is_admin(sent))


@app.post("/admin/backtests/delete", response_model=DeleteResult, dependencies=[Depends(require_admin)])
def delete_backtests(req: DeleteBacktestsRequest, session: SessionDep):
    return DeleteResult(deleted=repo.delete_backtests(session, None if req.delete_all else req.ids))


@app.get("/backtests", response_model=list[BacktestSummary])
def list_backtests(session: SessionDep, limit: Annotated[int, Query(ge=1, le=200)] = 50):
    return repo.list_backtests(session, limit)


@app.get("/backtests/{run_id}", response_model=BacktestDetail)
def get_backtest(run_id: int, session: SessionDep):
    run = repo.get_backtest(session, run_id)
    if run is None:
        raise HTTPException(404, "Backtest not found")
    return _with_benchmark(session, run)


@app.post("/research/pairs", response_model=PairScanResponse, dependencies=[Depends(heavy_slot)])
def pair_scan(req: PairScanRequest, session: SessionDep):
    tickers = [t.upper() for t in req.tickers]
    prices = repo.get_prices(session, tickers, str(req.start), str(req.end), allow_missing=True)
    skipped = [t for t in tickers if t not in prices.columns]
    if prices.shape[1] < 2:
        raise HTTPException(422, f"Need price data for at least 2 tickers (none for: {', '.join(skipped)})")
    table = scan_pairs(ffill_within_life(prices))
    table["half_life"] = table["half_life"].map(lambda x: x if math.isfinite(x) else None)
    return {"pairs": table.to_dict("records"), "skipped": skipped}


# ------------------------------------------------------------- paper bots
# Read-only: bots are stepped by the scheduled CLI (python -m quantlab.bot run).


def _bot_or_404(session: Session, name: str) -> dict:
    status = bot_store.status(session, name)
    if status is None:
        raise HTTPException(404, f"No bot named '{name}'")
    return status


@app.get("/bots", response_model=list[BotSummary])
def list_bots(session: SessionDep):
    out = []
    for row in bot_store.list_bots(session):
        curve = bot_store.equity_curve(session, row.name)
        last = curve[-1] if curve else None
        out.append(BotSummary(name=row.name, last_date=row.last_date, updated_at=row.updated_at,
                              equity=last.equity if last else None,
                              open_pairs=last.open_pairs if last else None))
    return out


@app.get("/bots/{name}", response_model=BotStatus)
def bot_status(name: str, session: SessionDep):
    return _bot_or_404(session, name)


@app.get("/bots/{name}/equity", response_model=list[BotEquityPoint])
def bot_equity(name: str, session: SessionDep):
    _bot_or_404(session, name)
    return bot_store.equity_curve(session, name)


@app.get("/bots/{name}/fills", response_model=list[BotFill])
def bot_fills(name: str, session: SessionDep, limit: Annotated[int, Query(ge=1, le=1000)] = 200):
    _bot_or_404(session, name)
    return bot_store.fills(session, name, limit)


@app.get("/bots/{name}/events", response_model=list[BotEventOut])
def bot_events(name: str, session: SessionDep, limit: Annotated[int, Query(ge=1, le=1000)] = 200):
    _bot_or_404(session, name)
    return bot_store.events(session, name, limit)
