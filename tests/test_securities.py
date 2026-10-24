from quantlab import securities
from quantlab.securities import Security, fold, load, search


def symbols(query: str, limit: int = 8) -> list[str]:
    return [s.symbol for s in search(query, limit)]


def test_the_shipped_list_is_sane():
    rows = load()
    assert len(rows) >= 500
    assert len({s.symbol for s in rows}) == len(rows)  # no symbol twice
    assert {s.kind for s in rows} == {"stock", "etf", "index"}
    assert all(s.symbol and s.name and s.group for s in rows)
    assert {e.symbol for e in securities.EXTRAS} <= {s.symbol for s in rows}
    assert "BRK-B" in {s.symbol for s in rows}  # Yahoo style, not BRK.B


def test_exact_symbol_comes_first_then_symbol_prefix_then_names():
    assert symbols("aapl")[0] == "AAPL"
    assert symbols("app")[:2] == ["APP", "AAPL"]  # APP is the symbol, Apple starts with "app"
    assert symbols("apple inc") == ["AAPL"]


def test_names_are_searched_by_start_word_and_substring():
    assert "MSFT" in symbols("micro")
    assert symbols("bank of")[0] == "BAC"
    assert "GOOGL" in symbols("alphabet") and "GOOG" in symbols("alphabet")
    assert symbols("alphabet")[0] == "GOOGL"  # Class A before Class C, alphabetically


def test_same_rank_name_matches_are_alphabetical():
    hits = search("micro", 5)
    names = [s.name for s in hits if s.name.lower().startswith("micro")]
    assert names == sorted(names, key=str.lower)


def test_caret_symbols_are_found_with_or_without_the_caret():
    assert symbols("gspc") == ["^GSPC"]
    assert symbols("^gspc") == ["^GSPC"]


def test_accents_and_case_do_not_matter():
    assert fold("Türk Hava Yolları") == "turk hava yollari"
    assert fold("İSTANBUL") == fold("istanbul")  # dotted capital I, as Turkish keyboards give it
    assert symbols("TUR")[0] == "TUR"


def test_blank_queries_and_limits():
    assert search("   ") == []
    assert search("") == []
    assert len(search("a", 3)) == 3
    assert search("zzzzzzzz") == []


def test_names_that_tie_are_listed_alphabetically():
    hits = search("ishares", 50)  # only ETFs start with it
    assert hits and all(s.kind == "etf" for s in hits)
    assert [s.name.lower() for s in hits] == sorted(s.name.lower() for s in hits)


def test_a_stock_is_listed_before_an_index_with_the_same_name_start():
    hits = search("s&p")
    assert hits[0].symbol == "SPGI"  # S&P Global, a stock, before the S&P 500 index and its ETFs


def test_a_security_is_plain_data():
    assert Security("X", "X Corp", "stock", "Sector") == Security("X", "X Corp", "stock", "Sector")
