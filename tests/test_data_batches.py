"""Yahoo downloads are split into batches (yfinance starts one thread per ticker)."""

import pandas as pd
import pytest
import yfinance

from quantlab import data


def _fake_download(calls):
    def fake(tickers, start, end, auto_adjust, progress):
        calls.append(list(tickers))
        idx = pd.date_range("2024-01-01", periods=3)
        cols = pd.MultiIndex.from_product([["Close"], tickers])
        return pd.DataFrame(1.0, index=idx, columns=cols)

    return fake


def test_download_is_split_into_batches(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(yfinance, "download", _fake_download(calls))
    monkeypatch.setattr(data, "YAHOO_BATCH", 2)

    tickers = ["E", "D", "C", "B", "A"]
    prices = data.load_prices(tickers, "2024-01-01", "2024-01-04", cache_dir=None)

    assert [len(c) for c in calls] == [2, 2, 1]
    assert list(prices.columns) == sorted(tickers)
    assert len(prices) == 3


def test_all_batches_empty_raises(monkeypatch):
    monkeypatch.setattr(yfinance, "download", lambda *a, **k: pd.DataFrame())
    with pytest.raises(ValueError, match="No price data"):
        data.load_prices(["AAA"], "2024-01-01", "2024-01-04", cache_dir=None)
