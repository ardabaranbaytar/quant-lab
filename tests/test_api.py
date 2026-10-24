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


@pytest.mark.parametrize(
    "patch",
    [
        {"tickers": ["AAA; DROP TABLE prices"]},
        {"tickers": ["A" * 40]},
        {"benchmark": "../../etc/passwd"},
        {"params": {"lookback": 10**9}},
        {"params": {"lookback": 1e30}},
        {"params": {"lookback": {"nested": 1}}},
        {"params": {"lookback": [1, 2]}},
        {"params": {f"p{i}": 1 for i in range(25)}},
        {"start": "1900-01-01", "end": "2022-01-01"},
    ],
)
def test_backtest_rejects_out_of_bounds_input(client, patch):
    body = {"strategy": "ts_momentum", "tickers": ["AAA"], "start": "2020-01-01", "end": "2022-01-01"}
    res = client.post("/backtests", json={**body, **patch})
    assert res.status_code == 422, res.text
    assert client.get("/backtests").json() == []  # nothing was stored


def test_pair_scan_rejects_bad_tickers_and_span(client):
    bad_ticker = {"tickers": ["PA", "x y"], "start": "2020-01-01", "end": "2022-01-01"}
    assert client.post("/research/pairs", json=bad_ticker).status_code == 422
    too_long = {"tickers": ["PA", "PB"], "start": "1900-01-01", "end": "2022-01-01"}
    assert client.post("/research/pairs", json=too_long).status_code == 422


def test_list_limits_are_bounded(client):
    assert client.get("/backtests?limit=200").status_code == 200
    assert client.get("/backtests?limit=201").status_code == 422
    assert client.get("/backtests?limit=0").status_code == 422


def test_stored_runs_are_pruned_to_the_newest(client, monkeypatch):
    import api.main

    monkeypatch.setattr(api.main, "MAX_STORED_RUNS", 2)
    body = {"strategy": "buy_and_hold", "tickers": ["AAA"], "start": "2020-01-01", "end": "2021-12-31"}
    ids = [client.post("/backtests", json=body).json()["id"] for _ in range(4)]
    listed = [r["id"] for r in client.get("/backtests").json()]
    assert listed == ids[:1:-1]  # newest two, newest first
    assert client.get(f"/backtests/{ids[0]}").status_code == 404


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


ADMIN_KEY = "k" * 32
RUN_BODY = {"strategy": "buy_and_hold", "tickers": ["AAA"], "start": "2020-01-01", "end": "2021-12-31"}


def _admin(key: str | None = ADMIN_KEY) -> dict[str, str]:
    return {"X-Admin-Token": key} if key else {}


def test_deleting_history_is_off_without_a_key(client, monkeypatch):
    monkeypatch.delenv("QUANTLAB_ADMIN_TOKEN", raising=False)
    run_id = client.post("/backtests", json=RUN_BODY).json()["id"]
    assert client.get("/admin/session").json() == {"enabled": False, "authorized": False}
    res = client.post("/admin/backtests/delete", json={"ids": [run_id]}, headers=_admin())
    assert res.status_code == 404
    assert client.get(f"/backtests/{run_id}").status_code == 200


def test_a_short_key_does_not_enable_deleting(client, monkeypatch):
    monkeypatch.setenv("QUANTLAB_ADMIN_TOKEN", "short")
    assert client.get("/admin/session", headers=_admin("short")).json() == {"enabled": False, "authorized": False}
    assert client.post("/admin/backtests/delete", json={"delete_all": True}, headers=_admin("short")).status_code == 404


def test_session_reports_whether_the_key_is_right(client, monkeypatch):
    monkeypatch.setenv("QUANTLAB_ADMIN_TOKEN", ADMIN_KEY)
    assert client.get("/admin/session").json() == {"enabled": True, "authorized": False}
    assert client.get("/admin/session", headers=_admin("x" * 32)).json() == {"enabled": True, "authorized": False}
    assert client.get("/admin/session", headers=_admin()).json() == {"enabled": True, "authorized": True}


def test_delete_needs_the_right_key(client, monkeypatch):
    monkeypatch.setenv("QUANTLAB_ADMIN_TOKEN", ADMIN_KEY)
    run_id = client.post("/backtests", json=RUN_BODY).json()["id"]
    for headers in ({}, _admin("x" * 32)):
        res = client.post("/admin/backtests/delete", json={"ids": [run_id]}, headers=headers)
        assert res.status_code == 401
    assert client.get(f"/backtests/{run_id}").status_code == 200  # still there


def test_delete_removes_the_chosen_runs_and_their_curves(client, monkeypatch):
    monkeypatch.setenv("QUANTLAB_ADMIN_TOKEN", ADMIN_KEY)
    first, second, third = (client.post("/backtests", json=RUN_BODY).json()["id"] for _ in range(3))
    res = client.post("/admin/backtests/delete", json={"ids": [first, third, 999]}, headers=_admin())
    assert res.status_code == 200
    assert res.json() == {"deleted": 2}  # the unknown id is ignored
    assert [r["id"] for r in client.get("/backtests").json()] == [second]
    assert client.get(f"/backtests/{first}").status_code == 404

    from sqlalchemy import func, select

    from quantlab.db.models import BacktestPoint
    from quantlab.db.session import session_scope

    with session_scope() as session:
        left = session.scalar(select(func.count()).select_from(BacktestPoint).where(BacktestPoint.run_id == first))
    assert left == 0


def test_delete_all_empties_the_history(client, monkeypatch):
    monkeypatch.setenv("QUANTLAB_ADMIN_TOKEN", ADMIN_KEY)
    for _ in range(3):
        client.post("/backtests", json=RUN_BODY)
    res = client.post("/admin/backtests/delete", json={"delete_all": True}, headers=_admin())
    assert res.json() == {"deleted": 3}
    assert client.get("/backtests").json() == []


@pytest.mark.parametrize("body", [{}, {"ids": []}, {"ids": ["a"]}, {"ids": list(range(501))}])
def test_delete_rejects_an_empty_or_oversized_request(client, monkeypatch, body):
    monkeypatch.setenv("QUANTLAB_ADMIN_TOKEN", ADMIN_KEY)
    assert client.post("/admin/backtests/delete", json=body, headers=_admin()).status_code == 422
