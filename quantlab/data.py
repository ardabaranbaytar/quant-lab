"""Price data loading with a local parquet cache."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

DEFAULT_CACHE_DIR = Path(".cache/prices")

# yfinance starts one OS thread per ticker (its worker limit only throttles how many run at
# once), so one call for the whole S&P 500 needs ~500 threads and dies with "can't start new
# thread" under the bot unit's TasksMax=256. Downloading in batches keeps the peak well below it.
YAHOO_BATCH = 100


def _cache_path(tickers: list[str], start: str, end: str, cache_dir: Path) -> Path:
    # MD5 only names a cache file; it is not used for any security purpose.
    raw = f"{','.join(tickers)}|{start}|{end}".encode()
    key = hashlib.md5(raw, usedforsecurity=False).hexdigest()[:16]
    return cache_dir / f"{key}.parquet"


def _download_close(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    import yfinance as yf

    frames = []
    for i in range(0, len(tickers), YAHOO_BATCH):
        batch = tickers[i : i + YAHOO_BATCH]
        raw = yf.download(batch, start=start, end=end, auto_adjust=True, progress=False)
        if raw.empty:
            continue
        close = raw["Close"]
        if isinstance(close, pd.Series):
            close = close.to_frame(batch[0])
        frames.append(close)
    if not frames:
        raise ValueError(f"No price data returned for {tickers}")
    return pd.concat(frames, axis=1)


def symbols_with_history(symbols: list[str]) -> set[str]:
    """Which of ``symbols`` Yahoo knows: those with any close in their whole history.

    Monthly bars keep the download small. "Any history" rather than "recent data" on purpose:
    delisted names still count, since a backtest over past dates is legitimate for them.
    Raises if Yahoo cannot be reached, so callers can tell "unknown symbol" from "no answer".
    """
    import yfinance as yf

    raw = yf.download(symbols, period="max", interval="1mo", auto_adjust=True, progress=False)
    if raw.empty:
        return set()
    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(symbols[0])
    return {str(c) for c in close.columns if close[c].notna().any()}


def load_prices(
    tickers: Iterable[str],
    start: str,
    end: str,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
) -> pd.DataFrame:
    """Download split/dividend-adjusted close prices (dates x tickers).

    Results are cached on disk so repeated research runs don't hit Yahoo again.
    Pass ``cache_dir=None`` to disable caching.
    """
    tickers = sorted({t.upper() for t in tickers})
    path = None
    if cache_dir is not None:
        path = _cache_path(tickers, start, end, Path(cache_dir))
        if path.exists():
            return pd.read_parquet(path)

    prices = _download_close(tickers, start, end).sort_index()
    prices.index = pd.DatetimeIndex(prices.index).tz_localize(None)
    prices.columns.name = None

    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        prices.to_parquet(path)
    return prices


def clean_prices(prices: pd.DataFrame, min_coverage: float = 0.0) -> pd.DataFrame:
    """Forward-fill gaps inside each ticker's life; optionally drop thin tickers.

    Leading NaNs (before listing) and trailing NaNs (after delisting) are kept,
    so strategies ignore a ticker until it lists and the engine can see when
    it dies. ``min_coverage`` > 0 drops short-lived tickers — which itself
    introduces survivorship bias, so it defaults to off.
    """
    from quantlab.engine import ffill_within_life

    coverage = prices.notna().mean()
    kept = prices.loc[:, coverage >= min_coverage]
    return ffill_within_life(kept)
