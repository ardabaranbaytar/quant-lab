import pandas as pd
import pytest

from quantlab.db import init_db, session_scope
from quantlab.db import repository as repo
from quantlab.db.session import get_engine
from quantlab.engine import run_backtest
from quantlab.metrics import performance_summary
from quantlab.strategies import ts_momentum


@pytest.fixture
def engine(tmp_path):
    eng = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(eng)
    return eng


def test_price_roundtrip(engine, prices):
    with session_scope(engine) as s:
        assert repo.save_prices(s, prices) == prices.size
    with session_scope(engine) as s:
        loaded = repo.load_prices(s, prices.columns, prices.index[0].date(), prices.index[-1].date())
    assert loaded.shape == prices.shape
    assert (loaded - prices).abs().max().max() < 1e-9


def test_get_prices_fetches_only_missing(engine, prices):
    calls = []

    def fake_fetch(tickers, start, end):
        calls.append(tickers)
        return prices[tickers]

    start, end = str(prices.index[0].date()), str(prices.index[-1].date())
    with session_scope(engine) as s:
        repo.get_prices(s, ["A", "B"], start, end, fetch=fake_fetch)
    with session_scope(engine) as s:
        out = repo.get_prices(s, ["a", "B", "C"], start, end, fetch=fake_fetch)
    assert calls == [["A", "B"], ["C"]]
    assert list(out.columns) == ["A", "B", "C"]


def test_save_and_list_backtest(engine, prices):
    result = run_backtest(prices, ts_momentum(prices, 60))
    metrics = performance_summary(result.net_returns)
    with session_scope(engine) as s:
        run = repo.save_backtest(
            s, strategy="ts_momentum", params={"lookback": 60}, tickers=list(prices.columns),
            cost_rate=0.001, result=result, metrics=metrics,
        )
        run_id = run.id
    with session_scope(engine) as s:
        loaded = repo.get_backtest(s, run_id)
        assert len(loaded.points) == len(result.net_returns)
        assert loaded.points[-1].equity == pytest.approx(result.equity.iloc[-1])
        assert [r.id for r in repo.list_backtests(s)] == [run_id]


def test_refresh_prices_adds_new_closes_and_overwrites_stale_bars(engine, prices):
    truth = prices[["A", "B"]]
    stored = truth.iloc[:-3].copy()
    stored.iloc[-1] *= 1.05  # an intraday bar saved while the market was open
    with session_scope(engine) as s:
        repo.save_prices(s, stored)
    end = truth.index[-2]  # the last bar (index[-1]) is "today", not closed yet

    def fake_fetch(tickers, start, stop):
        return truth.loc[start:stop, tickers]

    with session_scope(engine) as s:
        # get_prices alone would treat the 3-day gap as covered (holiday tolerance)
        assert repo.get_prices(s, ["A", "B"], str(truth.index[0].date()), str(end.date()),
                               fetch=fake_fetch).index[-1] < end
        repo.refresh_prices(s, ["A", "B"], str(truth.index[-10].date()), str(end.date()), fetch=fake_fetch)
    with session_scope(engine) as s:
        loaded = repo.load_prices(s, ["A", "B"], truth.index[0].date(), truth.index[-1].date())
    assert loaded.index[-1] == end
    pd.testing.assert_frame_equal(loaded, truth.loc[:end], check_freq=False, check_names=False,
                                  check_index_type=False)
