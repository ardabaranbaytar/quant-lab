# Stat-arb paper-trading bot

## Why run a strategy that has no edge?

The research ([pair portfolio](../reports/pair_portfolio.md), [edge search](../reports/edge_search.md))
found no after-cost edge for classic pairs trading in large caps. The bot is
therefore not a money-maker. It is:

- **a true out-of-sample test**: prices the strategy has never seen, arriving one day at a time;
- **a check that research code survives contact with a live loop**: next-day fills, delistings, restarts;
- **the base layer** that a future signal (or a paid data source) plugs into.

## Requirements

| # | Requirement | How it is met |
|---|---|---|
| R1 | Paper only, never real money | `PaperBroker` is an in-process simulator; no broker API keys exist |
| R2 | Same decisions as the backtest | shared `next_position` state machine; parity test replays history through the bot and must match `run_pair_portfolio` exactly |
| R3 | No look-ahead | orders decided on close *t* fill at close *t+1*; the CLI never processes a session before 16:15 New York time |
| R4 | No survivorship bias at selection | eligible tickers = point-in-time S&P 500 members on the selection date |
| R5 | Risk layer | `BreakMonitor` blocks entries on WARNING and exits on BROKEN (same as the backtest) |
| R6 | Restartable and idempotent | full state in `bot_states` after every day; a re-run skips processed days; resumed == uninterrupted (tested) |
| R7 | Auditable | every fill, pair event and daily mark stored in SQL (`paper_fills`, `bot_events`, `bot_equity`) |
| R8 | Data source swappable | the bot takes a price frame; where it comes from (Yahoo via `repository.get_prices` today) is the caller's concern |

## Architecture

```
scheduler (cron / Task Scheduler, weekdays after the close)
  └─ python -m quantlab.bot run --name sp500-pairs
       ├─ repository.get_prices  (MySQL cache, Yahoo for missing days)
       ├─ runner.run_bot         (every unprocessed close, in order)
       │    └─ StatArbBot.step(date)
       │         1. PaperBroker fills yesterday's orders at today's close
       │         2. every 63 days: close all pairs, re-select top 20
       │            (same sub-industry, Engle-Granger p < 0.05, half-life 5-60 days)
       │         3. per pair: z-score -> BreakMonitor (only when it matters) -> next_position
       │         4. new trades sized in shares (1/20 of equity, legs 1 : beta), net orders submitted
       └─ store.record_step      (bot_states, bot_equity, paper_fills, bot_events)

FastAPI (read-only)  GET /bots, /bots/{name}, /bots/{name}/equity|fills|events
```

| Module | Role |
|---|---|
| `quantlab/bot/config.py` | `BotConfig`, JSON-serialisable (stored with the bot) |
| `quantlab/bot/broker.py` | `PaperBroker`: cash, positions, pending orders, costs |
| `quantlab/bot/core.py` | `StatArbBot.step`: the daily loop |
| `quantlab/bot/store.py` | SQL persistence and queries |
| `quantlab/bot/runner.py` | catch-up loop, idempotent |
| `quantlab/bot/__main__.py` | CLI (`run`, `status`) |

## Simplifications (deliberate, documented)

- Fills at the next **close**, fractional shares, flat 10 bps cost on notional. There is no spread,
  market impact or borrow fee, so live results are an upper bound.
- Shares are frozen for the life of a trade, so position weights drift (the backtest rebalances
  to target weights; the parity test compares decisions, not dollar P&L).
- A delisted leg is closed at its last available close.
- GICS groups come from today's Wikipedia table, so they are correct for a bot that runs forward.

## Running it

```bash
python -m quantlab.bot run --name sp500-pairs          # first run: starts at the last close
python -m quantlab.bot run --name sp500-pairs          # later runs: process new closes only
python -m quantlab.bot status --name sp500-pairs
```

The first run downloads about 3 years of prices for about 500 tickers (~1 minute).
Every run re-downloads the last 10 days, so new closes always arrive and an intraday
bar saved by an earlier run is overwritten with the real close.

## Scheduling

The bot must run once per US trading day **after** the 16:00 New York close. New York
observes DST and Istanbul does not, so a fixed Istanbul time drifts by an hour: 23:30
TR is 16:30 NY in summer but 15:30 NY (before the close) in winter. Each option below is
DST-safe. Running late or twice is harmless: the CLI never processes an unfinished
session, skips days it has done and catches up on any it missed.

| Where | File | When |
|---|---|---|
| Your Windows PC (local MySQL) | `deploy/windows/register_bot_task.ps1` | Tue–Sat 00:30 Istanbul = 17:30 NY (summer) / 16:30 NY (winter); runs at next start-up if the PC was off |
| Linux server | `deploy/systemd/quantlab-bot.{service,timer}` | `Mon..Fri 16:30 America/New_York` |
| Linux server (cron) | `deploy/crontab.example` | `CRON_TZ=America/New_York`, 16:30 Mon–Fri |
| GitHub Actions | `.github/workflows/paper-bot.yml` | 21:30 UTC Mon–Fri = 17:30 / 16:30 NY; needs the `BOT_DATABASE_URL` secret pointing at a DB reachable from the internet, otherwise the job skips itself |

Output goes to `logs/bot.log` (git-ignored) for the local options, and to the job summary
on GitHub Actions. Use only one scheduler per database: two could step the same bot at once.
