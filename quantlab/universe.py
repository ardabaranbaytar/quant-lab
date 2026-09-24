"""Point-in-time index membership — the first line of defence against
survivorship bias.

Backtesting on *today's* S&P 500 list quietly selects the companies that
survived and grew; firms that shrank, failed or were acquired never enter the
sample. A point-in-time universe only lets a strategy choose among stocks that
were actually in the index on each date.

Membership data: github.com/fja05680/sp500 (MIT licence), one row per
membership spell: ``ticker, start_date, end_date`` (end empty = still in).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SP500_SPELLS_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/sp500_ticker_start_end.csv"
)
DEFAULT_CACHE = Path(".cache/universe/sp500_ticker_start_end.csv")


def _yahoo_symbol(ticker: str) -> str:
    return ticker.replace(".", "-").upper()


def load_sp500_spells(cache: Path | str | None = DEFAULT_CACHE, refresh: bool = False) -> pd.DataFrame:
    """Membership spells with Yahoo-style tickers (BRK.B -> BRK-B)."""
    path = Path(cache) if cache else None
    if path is not None and path.exists() and not refresh:
        raw = pd.read_csv(path)
    else:
        raw = pd.read_csv(SP500_SPELLS_URL)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(path, index=False)
    return normalise_spells(raw)


def normalise_spells(raw: pd.DataFrame) -> pd.DataFrame:
    spells = raw.rename(columns=str.lower)[["ticker", "start_date", "end_date"]].copy()
    spells["ticker"] = spells["ticker"].map(_yahoo_symbol)
    spells["start_date"] = pd.to_datetime(spells["start_date"])
    spells["end_date"] = pd.to_datetime(spells["end_date"])
    return spells


def members_on(spells: pd.DataFrame, date) -> list[str]:
    date = pd.Timestamp(date)
    active = (spells["start_date"] <= date) & (spells["end_date"].isna() | (spells["end_date"] > date))
    return sorted(spells.loc[active, "ticker"].unique())


def current_members(spells: pd.DataFrame) -> list[str]:
    """Today's constituents — the *biased* universe most tutorials use."""
    return sorted(spells.loc[spells["end_date"].isna(), "ticker"].unique())


def ever_members(spells: pd.DataFrame, start, end) -> list[str]:
    """Every ticker that was a member at any point in [start, end]."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    overlap = (spells["start_date"] <= end) & (spells["end_date"].isna() | (spells["end_date"] > start))
    return sorted(spells.loc[overlap, "ticker"].unique())


def membership_mask(spells: pd.DataFrame, index: pd.Index, tickers=None) -> pd.DataFrame:
    """Boolean frame (dates x tickers): True where the ticker was a member.

    A spell is [start_date, end_date): the day a stock is removed it is no
    longer eligible.
    """
    index = pd.DatetimeIndex(index)
    tickers = sorted(set(spells["ticker"])) if tickers is None else list(tickers)
    mask = pd.DataFrame(False, index=index, columns=tickers)
    rows = spells[spells["ticker"].isin(tickers)]
    open_end = index[-1] + pd.Timedelta(days=1)
    for ticker, start, end in zip(rows["ticker"], rows["start_date"], rows["end_date"]):
        stop = open_end if pd.isna(end) else end
        in_spell = (index >= start) & (index < stop)
        mask.loc[in_spell, ticker] = True
    return mask


SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
GICS_CACHE = Path(".cache/universe/sp500_gics.csv")


def load_sp500_gics(cache: Path | str | None = GICS_CACHE, refresh: bool = False) -> pd.DataFrame:
    """Current constituents' GICS sector / sub-industry (Wikipedia).

    Caveat: only *current* members are classified, so removed companies
    cannot be grouped — a residual survivorship bias for sector-based pairs.
    """
    path = Path(cache) if cache else None
    if path is not None and path.exists() and not refresh:
        cached = pd.read_csv(path)
        if "company" in cached.columns:
            return cached
    import io

    import requests

    html = requests.get(
        SP500_WIKI_URL, headers={"User-Agent": "quant-lab research (educational)"}, timeout=30
    ).text
    table = pd.read_html(io.StringIO(html))[0]
    out = pd.DataFrame({
        "ticker": table["Symbol"].map(_yahoo_symbol),
        # "News Corp (Class A)" -> "News Corp": identifies share classes.
        "company": table["Security"].str.replace(r"\s*\(Class [A-Z]\)", "", regex=True).str.strip(),
        "sector": table["GICS Sector"],
        "sub_industry": table["GICS Sub-Industry"],
    })
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False)
    return out


def coverage_report(mask: pd.DataFrame, prices: pd.DataFrame, dates=None) -> pd.DataFrame:
    """How many point-in-time members actually have price data on each date.

    The gap is the survivorship bias *left over* after using PIT membership:
    members the data vendor has dropped (typically failed or acquired firms).
    """
    dates = mask.index if dates is None else pd.DatetimeIndex(dates)
    available = prices.reindex(index=mask.index, columns=mask.columns).notna()
    members = mask.loc[dates].sum(axis=1)
    priced = (mask & available).loc[dates].sum(axis=1)
    return pd.DataFrame(
        {"members": members, "with_prices": priced, "coverage": priced / members.replace(0, pd.NA)}
    )
