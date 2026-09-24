"""CLI for the paper-trading bot.

    python -m quantlab.bot run    --name sp500-pairs [--start 2025-01-02] [--until 2025-06-30]
    python -m quantlab.bot status --name sp500-pairs

`run` is idempotent: schedule it once a day after the US close. A new bot
trades the point-in-time S&P 500, paired within GICS sub-industries.
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from quantlab.bot import store
from quantlab.bot.config import BotConfig
from quantlab.bot.runner import run_bot
from quantlab.db import init_db, session_scope
from quantlab.db import repository as repo
from quantlab.engine import ffill_within_life


def last_completed_session(now: pd.Timestamp | None = None) -> pd.Timestamp:
    """Latest date whose close is final. Before 16:15 New York time today's
    bar is still moving (Yahoo serves intraday prices), so it must not be
    processed: the bot would mark a live price as a close and skip it later."""
    now = pd.Timestamp.now(tz="America/New_York") if now is None else now.tz_convert("America/New_York")
    today = now.normalize().tz_localize(None)
    return today if (now.hour, now.minute) >= (16, 15) else today - pd.Timedelta(days=1)


def _run(args: argparse.Namespace) -> None:
    from quantlab.universe import load_sp500_gics, load_sp500_spells, members_on

    spells = load_sp500_spells(refresh=args.refresh_universe)
    with session_scope() as s:
        bot = store.load_bot(s, args.name)
        if bot is None:
            gics = load_sp500_gics(refresh=args.refresh_universe)
            config = BotConfig(groups=dict(zip(gics["ticker"], gics["sub_industry"])),
                               companies=dict(zip(gics["ticker"], gics["company"])),
                               capital=args.capital, break_monitor=not args.no_monitor)
            first = pd.Timestamp(args.start) if args.start else last_completed_session()
        else:
            assert bot.last_date is not None
            config, first = bot.config, bot.last_date
        end = min(pd.Timestamp(args.until), last_completed_session()) if args.until else last_completed_session()
        hist_start = first - pd.tseries.offsets.BDay(config.formation_days + 40)
        # Always re-fetch the recent tail: new closes + any intraday bar stored earlier.
        repo.refresh_prices(s, list(config.groups), str((first - pd.Timedelta(days=10)).date()),
                            str(end.date()))
        prices = repo.get_prices(s, list(config.groups), str(hist_start.date()),
                                 str((end + pd.Timedelta(days=1)).date()), allow_missing=True)
        prices = ffill_within_life(prices.loc[:end])
        reports = run_bot(s, args.name, prices, None if bot else config, start=first, until=end,
                          eligible=lambda d: set(members_on(spells, d)))
    for r in reports:
        evs = ", ".join(f"{e['event']} {e['pair']}" for e in r.events if e["event"] != "reselect")
        print(f"{r.date.date()}  equity {r.equity:>12,.0f}  open pairs {r.open_pairs:2d}  "
              f"orders {len(r.orders):2d}  {evs}")
    if not reports:
        print("nothing to do: no new closes since the last run")


def _status(args: argparse.Namespace) -> None:
    with session_scope() as s:
        st = store.status(s, args.name)
    if st is None:
        raise SystemExit(f"no bot named '{args.name}'")
    print(json.dumps(st, indent=2, default=str))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m quantlab.bot", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="process every new close")
    run.add_argument("--name", default="sp500-pairs")
    run.add_argument("--start", help="first trading day of a NEW bot (default: last close)")
    run.add_argument("--until", help="last day to process (default: last completed close)")
    run.add_argument("--capital", type=float, default=100_000.0)
    run.add_argument("--no-monitor", action="store_true", help="disable the break monitor")
    run.add_argument("--refresh-universe", action="store_true")
    status = sub.add_parser("status", help="print the current book")
    status.add_argument("--name", default="sp500-pairs")
    args = parser.parse_args(argv)
    init_db()
    {"run": _run, "status": _status}[args.cmd](args)


if __name__ == "__main__":
    main()
