from itertools import pairwise

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from quantlab.bot import BotConfig, PaperBroker, StatArbBot
from quantlab.bot import store as bot_store
from quantlab.bot.broker import Order
from quantlab.bot.runner import run_bot
from quantlab.db import init_db, session_scope
from quantlab.db.session import get_engine
from quantlab.risk import BreakMonitor
from quantlab.risk.synthetic import generate_pair
from quantlab.strategies.pair_portfolio import run_pair_portfolio

GROUPS = {"A1": "g1", "B1": "g1", "A2": "g2", "B2": "g2", "R1": "g1", "R2": "g2"}
KW = {"formation_days": 500, "top_k": 2, "max_pairs_per_stock": 1}


@pytest.fixture(scope="module")
def universe_prices():
    """Two cointegrated pairs + two unrelated random walks, over ~6 years."""
    p1 = generate_pair("stable", seed=1, n_days=1500).prices.rename(columns={"A": "A1", "B": "B1"})
    p2 = generate_pair("stable", seed=2, n_days=1500).prices.rename(columns={"A": "A2", "B": "B2"})
    rng = np.random.default_rng(9)
    noise = pd.DataFrame(50 * np.exp(np.cumsum(rng.normal(0, 0.015, (1500, 2)), axis=0)),
                         index=p1.index, columns=["R1", "R2"])
    return pd.concat([p1, p2, noise], axis=1)


def replay(prices: pd.DataFrame, config: BotConfig, first: int) -> tuple[StatArbBot, list]:
    bot = StatArbBot(config)
    reports = [bot.step(d, prices.loc[:d]) for d in prices.index[first:]]
    return bot, reports


@pytest.fixture(scope="module")
def replayed(universe_prices):
    config = BotConfig(groups=GROUPS, reselect_every=63, break_monitor=False, **KW)
    return replay(universe_prices, config, first=KW["formation_days"])


def test_bot_reproduces_backtest_positions(universe_prices, replayed):
    """Live/backtest parity: stepping day by day gives the backtest's book."""
    _, reports = replayed
    bt = run_pair_portfolio(universe_prices, GROUPS, trading_days=63, **KW).weights
    expected = bt.ffill().fillna(0.0).iloc[KW["formation_days"]:]
    got = pd.DataFrame([r.target_weights for r in reports], index=expected.index,
                       columns=expected.columns).fillna(0.0)
    assert (got != 0).any().any()
    pd.testing.assert_frame_equal(got, expected, check_exact=False, atol=1e-12)


def test_bot_matches_backtest_risk_exit():
    pair = generate_pair("death", seed=4, n_days=1300, break_at=1000).prices
    groups = {"A": "g", "B": "g"}
    bt = run_pair_portfolio(pair, groups, formation_days=756, top_k=1, break_monitor=BreakMonitor())
    config = BotConfig(groups=groups, formation_days=756, top_k=1, break_monitor=True)
    _, reports = replay(pair, config, first=756)
    exits = [str(r.date.date()) for r in reports for e in r.events if e["event"] == "risk_exit"]
    assert len(exits) == 1 and exits == [str(d.date()) for d in bt.risk_exits["date"]]


def test_orders_fill_at_next_close_with_costs(universe_prices, replayed):
    _, reports = replayed
    by_date = {r.date: r for r in reports}
    dates = [r.date for r in reports]
    fills = [f for r in reports for f in r.fills]
    assert fills
    for f in fills:
        fill_day = pd.Timestamp(f.fill_date)
        assert dates[dates.index(fill_day) - 1] == pd.Timestamp(f.order_date)
        assert f.price == pytest.approx(universe_prices.at[fill_day, f.ticker])
        assert f.cost == pytest.approx(abs(f.qty * f.price) * 0.001)
        assert any(o.ticker == f.ticker and o.qty == f.qty
                   for o in by_date[pd.Timestamp(f.order_date)].orders)


def test_equity_changes_only_by_pnl_and_costs(universe_prices, replayed):
    _, reports = replayed
    held: dict[str, float] = {}
    for prev, cur in pairwise(reports):
        for f in prev.fills:
            held[f.ticker] = held.get(f.ticker, 0.0) + f.qty
        dp = universe_prices.loc[cur.date] - universe_prices.loc[prev.date]
        pnl = sum(q * dp[t] for t, q in held.items())
        costs = sum(f.cost for f in cur.fills)
        assert cur.equity - prev.equity == pytest.approx(pnl - costs, abs=1e-6)
    # Shares are frozen per trade, so gross exposure drifts around 100% at most.
    assert max(r.gross_exposure for r in reports) < 1.25


def test_broker_roundtrip_and_delisted_order_stays_pending():
    broker = PaperBroker(cash=1000.0, cost_rate=0.0)
    broker.submit([Order("X", 2.0, "2024-01-02"), Order("GONE", -1.0, "2024-01-02")])
    fills = broker.fill_pending("2024-01-03", {"X": 10.0})
    assert [f.ticker for f in fills] == ["X"]
    assert broker.cash == 980.0 and broker.positions == {"X": 2.0}
    assert PaperBroker.from_dict(broker.to_dict()) == broker


def test_step_rejects_past_or_missing_dates(universe_prices):
    bot = StatArbBot(BotConfig(groups=GROUPS, break_monitor=False, **KW))
    d = universe_prices.index[600]
    bot.step(d, universe_prices)
    with pytest.raises(ValueError):
        bot.step(d, universe_prices)
    with pytest.raises(ValueError):
        bot.step(d + pd.Timedelta(days=1000 * 365), universe_prices)


@pytest.fixture
def engine(tmp_path):
    eng = get_engine(f"sqlite:///{tmp_path / 'bot.db'}")
    init_db(eng)
    return eng


def test_resumed_bot_equals_uninterrupted_bot(engine, universe_prices):
    config = BotConfig(groups=GROUPS, break_monitor=False, **KW)
    prices = universe_prices.iloc[:800]
    split = prices.index[650]
    with session_scope(engine) as s:
        run_bot(s, "once", prices, config, start=prices.index[500])
        run_bot(s, "split", prices, config, start=prices.index[500], until=split)
    with session_scope(engine) as s:  # new session = the next day's scheduled run
        assert run_bot(s, "split", prices.loc[:split]) == []  # idempotent
        run_bot(s, "split", prices)
        once = bot_store.equity_curve(s, "once")
        resumed = bot_store.equity_curve(s, "split")
        assert [p.date for p in once] == [p.date for p in resumed] and len(once) == 300
        assert [p.equity for p in once] == pytest.approx([p.equity for p in resumed], rel=1e-12)
        assert bot_store.status(s, "once")["positions"] == pytest.approx(
            bot_store.status(s, "split")["positions"], rel=1e-12)
        assert len(bot_store.fills(s, "once", limit=10_000)) == len(bot_store.fills(s, "split", limit=10_000))
    with session_scope(engine) as s, pytest.raises(ValueError):
        run_bot(s, "unknown", prices)


def test_bot_api(tmp_path, monkeypatch, universe_prices):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    get_engine.cache_clear()
    from api.main import app

    with TestClient(app) as client:
        with session_scope() as s:
            run_bot(s, "demo", universe_prices.iloc[:700],
                    BotConfig(groups=GROUPS, break_monitor=False, **KW), start=universe_prices.index[500])
        bots = client.get("/bots").json()
        assert [b["name"] for b in bots] == ["demo"] and bots[0]["equity"] > 0
        status = client.get("/bots/demo").json()
        assert status["last_date"] == str(universe_prices.index[699].date())
        assert status["config"]["top_k"] == 2 and status["config"]["universe_size"] == 6
        assert "groups" not in status["config"] and status["updated_at"]
        assert all(o["order_date"] == status["last_date"] for o in status["pending_orders"])
        assert len(client.get("/bots/demo/equity").json()) == 200
        assert client.get("/bots/demo/fills").json()
        assert any(e["event"] == "reselect" for e in client.get("/bots/demo/events").json())
        assert client.get("/bots/nope").status_code == 404
    get_engine.cache_clear()


def test_cli_never_processes_an_unfinished_session():
    from quantlab.bot.__main__ import last_completed_session

    ny = "America/New_York"
    assert last_completed_session(pd.Timestamp("2026-09-24 10:30", tz=ny)) == pd.Timestamp("2026-09-23")
    assert last_completed_session(pd.Timestamp("2026-09-24 16:20", tz=ny)) == pd.Timestamp("2026-09-24")
    # 17:30 in Istanbul is 10:30 in New York: still intraday.
    ist = pd.Timestamp("2026-09-24 17:30", tz="Europe/Istanbul")
    assert last_completed_session(ist) == pd.Timestamp("2026-09-23")
