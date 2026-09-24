import pytest
from fastapi.testclient import TestClient

import quantlab.data
from quantlab.db.session import get_engine


@pytest.fixture
def client(tmp_path, monkeypatch, prices, cointegrated_pair):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    get_engine.cache_clear()

    universe = prices.rename(columns={"A": "AAA", "B": "BBB", "C": "CCC", "D": "SPY"})
    universe = universe.join(cointegrated_pair.rename(columns={"A": "PA", "B": "PB"}), how="left")

    def fake_yahoo(tickers, start, end, cache_dir=None):
        # Mimic yfinance: unknown tickers are silently absent, all-unknown raises.
        known = [t for t in tickers if t in universe.columns]
        if not known:
            raise ValueError(f"No price data returned for {tickers}")
        return universe.loc[start:end, known].dropna(how="all")

    monkeypatch.setattr(quantlab.data, "load_prices", fake_yahoo)

    from api.main import app

    with TestClient(app) as c:
        yield c
    get_engine.cache_clear()


def test_health_and_strategies(client):
    assert client.get("/health").json() == {"status": "ok"}
    strategies = {s["name"]: s for s in client.get("/strategies").json()}
    assert strategies["ts_momentum"]["params"] == {"lookback": 60}
    assert strategies["pairs_trading"]["min_tickers"] == 2


def test_backtest_is_run_saved_and_listed(client):
    body = {
        "strategy": "ts_momentum",
        "tickers": ["aaa", "BBB"],
        "start": "2020-01-01",
        "end": "2022-11-15",
        "params": {"lookback": 40},
    }
    res = client.post("/backtests", json=body)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["tickers"] == ["AAA", "BBB"]
    assert data["params"] == {"lookback": 40}
    assert len(data["points"]) == len(data["benchmark"])
    assert "sharpe" in data["metrics"]

    listed = client.get("/backtests").json()
    assert [r["id"] for r in listed] == [data["id"]]
    assert "points" not in listed[0]
    saved = client.get(f"/backtests/{data['id']}").json()
    assert len(saved["points"]) == len(data["points"])
    assert saved["benchmark"] == data["benchmark"]
    assert saved["benchmark_metrics"] == data["benchmark_metrics"]


@pytest.mark.parametrize(
    "patch,fragment",
    [
        ({"strategy": "nope"}, "Unknown strategy"),
        ({"params": {"bogus": 1}}, "Unknown params"),
        ({"strategy": "pairs_trading", "tickers": ["AAA"]}, "at least 2"),
        ({"start": "2023-01-01", "end": "2022-01-01"}, "start must be before end"),
    ],
)
def test_backtest_validation_errors(client, patch, fragment):
    body = {"strategy": "ts_momentum", "tickers": ["AAA"], "start": "2020-01-01", "end": "2022-01-01"}
    res = client.post("/backtests", json={**body, **patch})
    assert res.status_code in (404, 422)
    assert fragment in res.text


def test_pair_scan_ranks_cointegrated_pair_first(client):
    res = client.post(
        "/research/pairs",
        json={"tickers": ["PA", "PB", "AAA", "NOPE"], "start": "2020-01-01", "end": "2022-11-15"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["pairs"][0]["pair"] == "PA-PB"
    assert res.json()["skipped"] == ["NOPE"]


def test_missing_backtest_returns_404(client):
    assert client.get("/backtests/999").status_code == 404


def test_heavy_endpoints_return_429_when_busy(client, monkeypatch):
    import threading

    import api.main

    monkeypatch.setattr(api.main, "_HEAVY_JOBS", threading.BoundedSemaphore(1))
    api.main._HEAVY_JOBS.acquire()  # one job already running
    body = {"strategy": "buy_and_hold", "tickers": ["AAA"], "start": "2020-01-01", "end": "2021-12-31"}
    assert client.post("/backtests", json=body).status_code == 429
    assert client.post("/research/pairs", json={"tickers": ["PA", "PB"], "start": "2019-01-01",
                                                "end": "2022-12-31"}).status_code == 429
    assert client.get("/bots").status_code == 200  # read-only endpoints are never limited
    api.main._HEAVY_JOBS.release()
    assert client.post("/backtests", json=body).status_code == 201
