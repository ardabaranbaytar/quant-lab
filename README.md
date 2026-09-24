# quant-lab

[![CI](https://github.com/ardabaranbaytar/quant-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/ardabaranbaytar/quant-lab/actions/workflows/ci.yml)

Portfolio-level backtesting, factor research and a statistical-arbitrage paper-trading bot — one codebase, from research notebook to deployed app.

> Work in progress. Consolidates four earlier research repos
> (multi-strategy framework, momentum, pairs trading, factor research).

## Status

- [x] `quantlab` core: data cache, portfolio-weight backtest engine, metrics
- [x] Strategies: buy & hold, time-series momentum, mean reversion, cross-sectional momentum, pairs trading
- [x] Research: rank IC, quantile spreads, pair scanning (cointegration, half-life)
- [x] Walk-forward / out-of-sample validation
- [x] MySQL storage + FastAPI
- [x] React dashboard (backtest, run history & comparison, pair scanner)
- [x] Point-in-time S&P 500 universe + delisting-aware engine
- [x] Break lab: synthetic pairs with known breaks + 7-detector break monitor
- [x] Real-world break case studies ([report](reports/case_studies.md))
- [x] Multi-pair portfolio with quarterly re-selection ([report](reports/pair_portfolio.md))
- [x] ML entry filter, purged walk-forward + placebo ([report](reports/ml_filter.md))
- [x] Avellaneda-Lee residual stat-arb, ETF pairs, turnover tuning with a locked hold-out ([report](reports/al_tuning.md))
- [x] Stat-arb paper-trading bot: paper broker, daily loop, SQL persistence, CLI, read-only API ([design](docs/paper_bot.md))
- [x] Bot dashboard page: equity curve, open book, fills, BreakMonitor events
- [x] CI (GitHub Actions: ruff, bandit, mypy, pytest, web lint + build) and daily bot scheduling (Actions cron, systemd timer or Windows Task Scheduler — [deploy/](deploy/))

## Design

Every strategy is a function `prices -> target weights` (dates × tickers). The
engine trades to those weights at each close, earns the **next** day's return,
lets holdings drift between rebalances and charges costs on actual turnover.
Long, short and multi-asset portfolios all go through the same code path.

```python
from quantlab.data import load_prices
from quantlab.engine import run_backtest
from quantlab.metrics import performance_summary
from quantlab.strategies import pairs_trading

prices = load_prices(["V", "MA"], "2015-01-01", "2024-12-31")
result = run_backtest(prices, pairs_trading(prices, "V", "MA"), cost_rate=0.001)
print(performance_summary(result.net_returns, turnover=result.turnover))
```

## Notable findings

**Survivorship bias ([full report](reports/survivorship.md)).** The same monthly
momentum strategy (top 20 by 60-day return, 2010–2024):

| Universe | Total return | CAGR | Sharpe |
|---|---:|---:|---:|
| Today's S&P 500 constituents (typical tutorial setup) | 2616% | 25.1% | 1.09 |
| Point-in-time S&P 500 membership | 314% | 10.1% | 0.55 |
| SPY buy & hold | 557% | 13.6% | 0.83 |

45% of the biased version's positions were in stocks *not yet in the index* —
TSLA, SMCI, AXON… bought because we already know they will become large caps.
Even the point-in-time result is an upper bound: 27% of historical members have
no free price data (mostly failed or acquired firms), which is why the engine
supports delisting returns for when a full-history data source is plugged in.

**Detecting pairs that break for good ([full report](reports/break_lab.md)).**
A z-score of −4 is either the best trade of the year or a company dying. The
break monitor combines seven causal detectors (rolling Dickey-Fuller, CUSUM,
z persistence, correlation drop, divergence, idiosyncratic volatility, trend
t-stat), each calibrated to a 1% daily false-flag rate on stable pairs, and
requires three to agree on 8 of 10 days. On 100 synthetic pairs per scenario:

| Scenario | Caught ≤ 6 months | Worst-5% return: naive → with monitor |
|---|---:|---:|
| Company collapse | 82% (median 78 days) | −56.6% → −17.4% |
| Hedge-ratio re-rating | 96% (median 34 days) | −19.9% → −10.9% |
| Stable pair (false alarm) | 8% of paths | mean return 24.9% → 24.6% |
| Temporary 4.5σ shock (missed opportunity) | 31% of paths | mean return 28.3% → 23.7% |

Building it exposed a quieter bug: a 1-year rolling OLS hedge ratio is so noisy
on autocorrelated spreads that stable pairs look broken (spread volatility 4×
the truth). A 3-year window fixes it — and alone turns the V–MA backtest from
−11.0% to +4.0%.

**Honest baseline: classic pairs trading has no edge in large caps anymore
([report](reports/pair_portfolio.md)).** Quarterly re-selection of the 20 best
cointegrated same-sub-industry pairs on the point-in-time S&P 500 (2013–2024)
is market-neutral (beta to SPY ≈ 0.03) but earns a Sharpe of 0.16 *before*
costs and slightly negative after 10 bps — consistent with the literature on
the decay of pairs-trading profits. Its one good year is 2020 (+7.8%), when
dislocations were large. The break monitor cannot fix a strategy without an
edge; that is the next research problem.

**An ML filter that didn't work — and how we know ([report](reports/ml_filter.md)).**
Every entry signal became a training example (21 entry-time features incl. the
break detectors; label = trade profitable after costs). Purged, yearly
walk-forward: a small first dataset (1,334 trades) gave AUC 0.52–0.53 and a
tempting per-trade spread, but a placebo run confirmed no leakage *and* the
3× larger dataset (4,298 trades) collapsed to AUC ≈ 0.49. Yearly AUC also
flipped below 0.5 in 2022–23 as the rate regime changed. Conclusion: with
price-based features, individual pair-trade outcomes are not predictable here.

**Edge search with a locked hold-out ([edge search](reports/edge_search.md), [tuning](reports/al_tuning.md)).**
Avellaneda-Lee (2010) residual stat-arb with the paper's own parameters has a
real *gross* edge in 2013–2018 (Sharpe 1.22) but trades ~180× its capital a
year, so 5 bps per side turns it negative. Turnover controls were tuned on
2013–2018 only (24 variants; best: net Sharpe +0.32, turnover 46×) and the
2019–2024 hold-out was opened once: net Sharpe −0.14, the gross edge having
decayed to 0.15. ETF pairs showed no gross edge at all. With free daily data
on large caps, none of the classic stat-arb approaches survives costs
out-of-sample — the tuned result would have looked like a success without the
hold-out.

**Look-ahead in pairs trading.**

The original V–MA pairs backtest estimated its hedge ratio on the full sample
(look-ahead bias) and reported **+86.8%**. With a rolling 252-day hedge ratio
frozen per trade, the same rules return **−11.0%** over 2015–2024. Fixing
this bias is the starting point for the stat-arb bot.

## Paper-trading bot

The multi-pair strategy runs forward one close at a time against a simulated
broker ([design and requirements](docs/paper_bot.md)). Orders decided on a
close fill at the **next** close; pairs are re-selected quarterly from the
point-in-time S&P 500; the break monitor gates entries and forces exits. Bot and
backtest share one decision function, and a parity test replays history
through the bot and requires the backtest's positions exactly. Given the
research above, this is an out-of-sample test, not a profit engine.

```bash
python -m quantlab.bot run --name sp500-pairs     # idempotent; schedule after the US close
python -m quantlab.bot status --name sp500-pairs
```

Scheduling options (all DST-safe, all after the 16:00 New York close) are in
[docs/paper_bot.md](docs/paper_bot.md#scheduling).

## Development

```bash
# backend
python -m venv .venv
.venv/Scripts/pip install -e ".[api,dev]"   # Windows; use .venv/bin on macOS/Linux
cp .env.example .env                         # MySQL credentials (falls back to SQLite)
uvicorn api.main:app --port 8000
# quality gate: lint -> security -> types -> tests
ruff check --fix . && bandit -r . -ll && mypy . && pytest

# frontend (proxies /api to :8000)
cd web && npm install && npm run dev         # http://localhost:5173
```

Deploying to a VPS (Caddy + systemd + MySQL, one script): [docs/deploy.md](docs/deploy.md).

Tests use synthetic data only (no network) and include explicit look-ahead
checks: perturbing future prices must never change past weights.

*Educational and research use only. Not investment advice.*
