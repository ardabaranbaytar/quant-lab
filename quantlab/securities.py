"""Searchable list of securities for the ticker picker: today's S&P 500 plus common ETFs and indices.

The list is a CSV in the repo (``securities.csv``), so the API answers instantly and offline.
Refresh it when the index changes:  ``python -m quantlab.securities``
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).with_name("securities.csv")
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

KIND_ORDER = {"stock": 0, "etf": 1, "index": 2}


@dataclass(frozen=True)
class Security:
    symbol: str  # Yahoo-style: BRK-B, ^GSPC
    name: str
    kind: str  # "stock" | "etf" | "index"
    group: str  # GICS sector for stocks, a short category for ETFs and indices


# Not part of the S&P 500 table: the broad ETFs and indices people backtest against.
EXTRAS: list[Security] = [
    Security("SPY", "SPDR S&P 500 ETF Trust", "etf", "US equity"),
    Security("IVV", "iShares Core S&P 500 ETF", "etf", "US equity"),
    Security("VOO", "Vanguard S&P 500 ETF", "etf", "US equity"),
    Security("VTI", "Vanguard Total Stock Market ETF", "etf", "US equity"),
    Security("QQQ", "Invesco QQQ Trust (Nasdaq-100)", "etf", "US equity"),
    Security("DIA", "SPDR Dow Jones Industrial Average ETF", "etf", "US equity"),
    Security("IWM", "iShares Russell 2000 ETF", "etf", "US equity"),
    Security("MDY", "SPDR S&P MidCap 400 ETF", "etf", "US equity"),
    Security("XLK", "Technology Select Sector SPDR Fund", "etf", "Sector"),
    Security("XLF", "Financial Select Sector SPDR Fund", "etf", "Sector"),
    Security("XLE", "Energy Select Sector SPDR Fund", "etf", "Sector"),
    Security("XLV", "Health Care Select Sector SPDR Fund", "etf", "Sector"),
    Security("XLI", "Industrial Select Sector SPDR Fund", "etf", "Sector"),
    Security("XLP", "Consumer Staples Select Sector SPDR Fund", "etf", "Sector"),
    Security("XLY", "Consumer Discretionary Select Sector SPDR Fund", "etf", "Sector"),
    Security("XLU", "Utilities Select Sector SPDR Fund", "etf", "Sector"),
    Security("XLB", "Materials Select Sector SPDR Fund", "etf", "Sector"),
    Security("XLRE", "Real Estate Select Sector SPDR Fund", "etf", "Sector"),
    Security("XLC", "Communication Services Select Sector SPDR Fund", "etf", "Sector"),
    Security("VNQ", "Vanguard Real Estate ETF", "etf", "Sector"),
    Security("EFA", "iShares MSCI EAFE ETF", "etf", "International"),
    Security("EEM", "iShares MSCI Emerging Markets ETF", "etf", "International"),
    Security("VEA", "Vanguard FTSE Developed Markets ETF", "etf", "International"),
    Security("VWO", "Vanguard FTSE Emerging Markets ETF", "etf", "International"),
    Security("EWG", "iShares MSCI Germany ETF", "etf", "International"),
    Security("TUR", "iShares MSCI Turkey ETF", "etf", "International"),
    Security("TLT", "iShares 20+ Year Treasury Bond ETF", "etf", "Bonds"),
    Security("IEF", "iShares 7-10 Year Treasury Bond ETF", "etf", "Bonds"),
    Security("SHY", "iShares 1-3 Year Treasury Bond ETF", "etf", "Bonds"),
    Security("AGG", "iShares Core U.S. Aggregate Bond ETF", "etf", "Bonds"),
    Security("LQD", "iShares iBoxx $ Investment Grade Corporate Bond ETF", "etf", "Bonds"),
    Security("HYG", "iShares iBoxx $ High Yield Corporate Bond ETF", "etf", "Bonds"),
    Security("GLD", "SPDR Gold Shares", "etf", "Commodities"),
    Security("SLV", "iShares Silver Trust", "etf", "Commodities"),
    Security("USO", "United States Oil Fund", "etf", "Commodities"),
    Security("^GSPC", "S&P 500 Index", "index", "US index"),
    Security("^DJI", "Dow Jones Industrial Average", "index", "US index"),
    Security("^IXIC", "NASDAQ Composite", "index", "US index"),
    Security("^NDX", "NASDAQ-100", "index", "US index"),
    Security("^RUT", "Russell 2000", "index", "US index"),
    Security("^VIX", "CBOE Volatility Index", "index", "US index"),
    Security("^FTSE", "FTSE 100", "index", "International"),
    Security("^GDAXI", "DAX (Germany)", "index", "International"),
    Security("XU100.IS", "BIST 100 (Borsa Istanbul)", "index", "International"),
]


def fold(text: str) -> str:
    """Lower-case, accent-free text for matching ("Türk" -> "turk")."""
    decomposed = unicodedata.normalize("NFKD", text.casefold().replace("ı", "i"))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def load() -> tuple[Security, ...]:
    with DATA_FILE.open(encoding="utf-8", newline="") as fh:
        return tuple(Security(**row) for row in csv.DictReader(fh))


def search(query: str, limit: int = 8) -> list[Security]:
    """Best matches first: exact symbol, symbol prefix, name start, a word of the name, then anywhere in it.

    Within a rank stocks come before ETFs and indices; symbol matches then go by the shorter
    symbol, name matches alphabetically.
    """
    q = fold(query).strip()
    if not q:
        return []
    bare = q.lstrip("^")
    ranked: list[tuple[int, int, int, str, Security]] = []
    for sec in load():
        symbol = fold(sec.symbol).lstrip("^")  # "gspc" finds ^GSPC
        name = fold(sec.name)
        if symbol == bare:
            rank = 0
        elif symbol.startswith(bare):
            rank = 1
        elif name.startswith(q):
            rank = 2
        elif any(word.startswith(q) for word in re.findall(r"[a-z0-9]+", name)):
            rank = 3
        elif q in name:
            rank = 4
        else:
            continue
        by_symbol = rank < 2
        ranked.append((rank, KIND_ORDER[sec.kind], len(symbol) if by_symbol else 0, symbol if by_symbol else name, sec))
    ranked.sort(key=lambda item: item[:4])
    return [item[4] for item in ranked[:limit]]


def build(path: Path = DATA_FILE) -> int:
    """Rewrite the CSV from the current S&P 500 table on Wikipedia plus ``EXTRAS``."""
    import pandas as pd
    import requests

    html = requests.get(
        SP500_WIKI_URL, headers={"User-Agent": "quant-lab research (educational)"}, timeout=30
    ).text
    table = pd.read_html(io.StringIO(html))[0]
    stocks = [
        Security(str(sym).replace(".", "-").upper(), str(name).strip(), "stock", str(sector))
        for sym, name, sector in zip(table["Symbol"], table["Security"], table["GICS Sector"], strict=True)
    ]
    rows = sorted(stocks, key=lambda s: s.symbol) + EXTRAS
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["symbol", "name", "kind", "group"])
        writer.writerows([s.symbol, s.name, s.kind, s.group] for s in rows)
    load.cache_clear()
    return len(rows)


if __name__ == "__main__":
    print(f"wrote {build()} securities to {DATA_FILE}")
