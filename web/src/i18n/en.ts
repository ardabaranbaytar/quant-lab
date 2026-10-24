// English is the source of truth: `Messages` is its shape, and tr.ts / de.ts must
// match it exactly (a missing key is a compile error).

interface StrategyText {
  name: string
  description: string
}

interface ParamText {
  label: string
  hint?: string
}

interface EventText {
  label: string
  hint: string
}

export const en = {
  language: 'Language',
  nav: { backtest: 'Backtest', history: 'History', pairs: 'Pair scanner', bot: 'Paper bot' },
  theme: { light: '☀ Light', dark: '☾ Dark', toLight: 'Switch to light theme', toDark: 'Switch to dark theme' },
  footer: 'Research and education only — not investment advice. Data: Yahoo Finance.',

  common: {
    start: 'Start',
    end: 'End',
    tickers: 'Tickers',
    strategy: 'Strategy',
    pair: 'Pair',
    buy: 'Buy',
    sell: 'Sell',
    long: 'Long',
    short: 'Short',
    none: 'None.',
    loading: 'Loading',
    error: 'Error',
    showMore: (left: number) => `Show more (${left} left)`,
    tickerExample: 'e.g. AAPL, MSFT',
    addTicker: 'Add ticker',
    removeTicker: (ticker: string) => `Remove ${ticker}`,
    checkingTicker: 'Checking…',
    tickerNotFound: (list: string) => `No price data found for ${list}`,
    tickerBadFormat: (list: string) => `Not a valid ticker: ${list}`,
    benchmark: 'SPY (buy & hold)',
  },

  errors: {
    network: 'Cannot reach the API. Is the backend running?',
    busy: 'Server busy: too many backtests running. Try again in a moment.',
  },

  time: {
    justNow: 'just now',
    minAgo: (n: number) => `${n} min ago`,
    hoursAgo: (n: number) => `${n} h ago`,
    daysAgo: (n: number) => `${n} d ago`,
  },

  // Keyed by the strategy name the API sends; unknown names fall back to the server text.
  strategies: {
    buy_and_hold: { name: 'Buy And Hold', description: 'Equal-weight, bought on day one and left to drift.' },
    ts_momentum: {
      name: 'TS Momentum',
      description: 'Long an asset while its trailing lookback-day return is positive.',
    },
    mean_reversion: {
      name: 'Mean Reversion',
      description: 'Long an asset while it trades more than threshold below its SMA.',
    },
    cross_sectional_momentum: {
      name: 'Cross Sectional Momentum',
      description: 'Each month-end, hold the top_n best performers equally weighted.',
    },
    pairs_trading: {
      name: 'Pairs Trading',
      description: 'Long/short the spread A - beta * B when its z-score is stretched.',
    },
  } as Record<string, StrategyText>,

  params: {
    lookback: { label: 'Lookback', hint: 'Trading days of past return used for the signal' },
    top_n: { label: 'Top N', hint: 'Number of winners held each month' },
    skip_days: { label: 'Skip days', hint: 'Most recent days excluded (12-1 momentum uses ~21)' },
    window: { label: 'Window', hint: 'Moving-average length in days' },
    threshold: { label: 'Threshold', hint: 'Distance below the SMA that triggers a buy (0.05 = 5%)' },
    asset_a: { label: 'Asset A', hint: 'Defaults to ticker order' },
    asset_b: { label: 'Asset B', hint: 'Defaults to ticker order' },
    hedge_window: { label: 'Hedge window', hint: 'Days of history for the rolling hedge ratio' },
    z_window: { label: 'Z window', hint: 'Days used to normalise the spread' },
    entry_z: { label: 'Entry z', hint: 'Open a trade when |z| exceeds this' },
    exit_z: { label: 'Exit z', hint: 'Close when z crosses back through this' },
    stop_z: { label: 'Stop z', hint: 'Optional stop-loss on |z| (blank = none)' },
  } as Record<string, ParamText>,

  metrics: {
    total_return: 'Total return',
    cagr: 'CAGR',
    sharpe: 'Sharpe',
    max_drawdown: 'Max drawdown',
    volatility: 'Volatility',
    sortino: 'Sortino',
    calmar: 'Calmar',
    hit_rate: 'Hit rate',
    annual_turnover: 'Annual turnover',
  } as Record<string, string>,

  backtest: {
    presets: {
      spyTrend: 'SPY trend',
      megaCap: 'Mega-cap momentum',
      pairs: 'V / MA pairs',
      sectorEtfs: 'Sector ETFs mean-rev',
    },
    configure: 'Configure',
    needsAtLeast: (n: number) => `Needs at least ${n}`,
    parameters: 'Parameters',
    auto: 'Auto',
    noValue: 'none',
    costs: 'Costs (bps)',
    riskFree: 'Risk-free (%)',
    compareSpy: 'Compare with SPY',
    run: 'Run backtest',
    running: 'Running…',
    fetching: 'Fetching prices and running the backtest…',
    emptyTitle: 'Backtest a strategy',
    emptyText: 'Start from a preset below, or build your own strategy on the left.',
    presetText: {
      spyTrend: 'Hold SPY while its 60-day return is positive.',
      megaCap: 'Each month, hold the 5 strongest of 15 US mega-caps.',
      pairs: 'Trade the Visa / Mastercard price gap when it stretches.',
      sectorEtfs: 'Buy sector ETFs trading 5% below their 20-day average.',
    },
    runPreset: 'Run →',
    principles: [
      { title: 'No look-ahead', text: 'Signals only use what was known at each close.' },
      { title: 'Costs included', text: 'Trading costs are charged on actual turnover.' },
      { title: 'Prices cached', text: 'Downloaded once, then stored in MySQL.' },
    ] as { title: string; text: string }[],
  },

  result: {
    savedAs: (id: number) => `Saved as run #${id} →`,
    costs: (bps: number) => `costs ${bps} bps`,
    moreTickers: (n: number) => `+${n} more`,
    totalReturn: 'Total return',
    cagr: 'CAGR',
    sharpeRatio: 'Sharpe ratio',
    maxDrawdown: 'Max drawdown',
    vsSpy: (delta: string) => `${delta} vs SPY`,
    spyValue: (value: string) => `SPY ${value}`,
    allMetrics: 'All metrics',
    metric: 'Metric',
    strategy: 'Strategy',
  },

  charts: {
    performance: 'Performance',
    comparison: 'Comparison',
    chart: 'Chart',
    yearlyTable: 'Yearly table',
    year: 'Year',
    growthOf: 'Growth of $1',
    logScale: 'Log scale',
    drawdownFromPeak: 'Drawdown from peak',
  },

  history: {
    title: 'Saved backtests',
    subtitle: (max: number) => `Every run is stored in MySQL. Select up to ${max} to compare their equity curves.`,
    noRuns: 'No runs yet. ',
    firstRun: 'Run your first backtest →',
    run: 'Run',
    period: 'Period',
    return: 'Return',
    sharpe: 'Sharpe',
    maxDd: 'Max DD',
    compareRun: (id: number) => `Compare run ${id}`,
    allRuns: '← All runs',
    admin: {
      open: 'Admin',
      keyLabel: 'Admin key',
      unlock: 'Unlock',
      wrongKey: 'That key is not right.',
      signOut: 'Sign out',
      delete: 'Delete',
      deleteRun: (id: number) => `Delete run ${id}`,
      deleteAll: 'Delete all',
      confirmAll: 'Delete every saved run?',
      confirmYes: 'Yes, delete',
      cancel: 'Cancel',
      rejected: 'The key was rejected. Sign in again.',
    },
  },

  pairs: {
    universes: {
      payments: 'Payments',
      banks: 'Banks',
      energy: 'Energy',
      staples: 'Staples',
      retail: 'Retail',
    },
    universe: 'Universe',
    pairsToTest: (n: number, max: number) => `${n} pairs will be tested (max ${max} tickers)`,
    scan: 'Scan pairs',
    scanning: 'Scanning…',
    lookAheadTitle: 'Avoid look-ahead:',
    lookAheadText:
      'choose pairs on an in-sample window (default 2015–2019), then backtest them on later data. Picking pairs on the same period you trade them inflates results.',
    running: (n: number) => `Running ${n} Engle–Granger cointegration tests…`,
    skipped: 'Skipped · ',
    noPriceData: (list: string) => `no price data for ${list}`,
    candidates: 'Candidate pairs',
    cointegratedCount: (n: number, total: number, level: string) => `${n} of ${total} cointegrated at ${level}`,
    cointP: 'Coint. p-value',
    returnCorr: 'Return corr.',
    hedgeRatio: 'Hedge ratio',
    halfLife: 'Half-life',
    days: (n: string) => `${n} d`,
    cointegrated: '(cointegrated)',
    backtestOos: 'Backtest out-of-sample →',
    emptyTitle: 'Find cointegrated pairs',
    emptyText:
      'Tests every pair in the universe for a stable long-run relationship (Engle–Granger), and estimates how quickly the spread mean-reverts.',
  },

  bot: {
    emptyTitle: 'No paper bot yet',
    emptyText:
      'Bots are stepped by a scheduled job, not from the browser. Start one from the backend folder; it trades the point-in-time S&P 500 from the last completed close:',
    emptyHint: 'Re-run it after each US close (it skips days already processed).',
    title: 'Paper-trading bot',
    upToDate: 'up to date',
    stale: (days: number) => `stale · ${days} days`,
    subtitle: 'Multi-pair stat-arb run forward one close at a time against a simulated broker. Paper money only.',
    botSelect: 'Bot',
    refresh: 'Refresh',
    refreshing: 'Refreshing…',
    noNewClose: (date: string) => `No new close since ${date}. Is the daily job running?`,

    status: {
      equity: 'Equity',
      sinceStart: (ret: string) => `${ret} since start`,
      openPairs: 'Open pairs',
      pairsInBook: (n: number) => `${n} pairs in the current book`,
      grossExposure: 'Gross exposure',
      cash: (amount: string) => `cash ${amount}`,
      lastBar: 'Last bar',
      ran: (ago: string) => `run ${ago}`,
      riskExits: 'Risk exits',
      nextReselect: (days: number) => `next re-selection in ${days} trading day${days === 1 ? '' : 's'}`,
    },

    equity: {
      title: 'Equity curve',
      equity: 'Equity',
      exposure: 'Exposure',
      return: 'Return',
      drawdown: 'Drawdown',
      grossExposure: 'Gross exposure',
      openPairs: 'Open pairs',
      needTwoCloses: 'The curve appears after the bot has processed two closes.',
      equityCaption: "Mark-to-market after each day's fills · dashed line = starting capital",
      exposureCaption: 'Gross exposure (area, left) and open pairs (line, right)',
      maxDrawdown: (value: string) => `max drawdown ${value}`,
    },

    book: {
      title: 'Open book',
      empty: 'No open pair trades — every pair is inside its entry band.',
      spread: 'Spread',
      legA: 'Leg A',
      legB: 'Leg B',
      since: 'Since',
      pending: 'Pending orders',
      pendingNote: '· fill at the next close',
    },

    config: {
      title: 'Configuration',
      breakMonitorOn: (votes: number, of: number) => `Break monitor on · ${votes}/${of} votes`,
      breakMonitorOff: 'Break monitor off',
      universe: 'Universe',
      universeValue: (n: number) => `${n} tickers · point-in-time S&P 500`,
      pairing: 'Pairing',
      pairingValue: 'Same GICS sub-industry, Engle-Granger on log prices',
      selection: 'Selection',
      selectionValue: (p: string, from: number, to: number) => `p < ${p}, half-life ${from}–${to} days`,
      book: 'Book',
      bookValue: (top: number, perStock: number) => `top ${top} pairs, ≤ ${perStock} per stock, 1/${top} of equity each`,
      formation: 'Formation',
      formationValue: (days: number, every: number) => `${days} trading days, re-selected every ${every}`,
      entryExit: 'Entry / exit',
      entryExitValue: (entry: string, exit: string) => `|z| > ${entry} · exit at z = ${exit}`,
      stop: 'Stop',
      stopNone: 'none (break monitor handles tail risk)',
      stopValue: (z: string) => `|z| > ${z}`,
      execution: 'Execution',
      executionValue: (bps: number) => `next close · ${bps} bps per side`,
      capital: 'Starting capital',
    },

    events: {
      title: 'Events',
      all: 'All',
      risk: 'Risk',
      trade: 'Trades',
      selection: 'Selection',
      riskNote:
        'Forced exits come from the BreakMonitor: seven causal detectors, a pair is closed when enough of them agree on 8 of the last 10 days. A z-stop or a delisted leg also counts as a risk exit.',
      noRisk: 'No risk exits so far — no pair has broken.',
      none: 'No events.',
      allPairs: 'All pairs',
      kinds: {
        risk_exit: {
          label: 'Forced exit',
          hint: 'BreakMonitor flagged the pair BROKEN: position closed, pair blocked until the detectors go quiet.',
        },
        delisted: { label: 'Delisted leg', hint: 'A leg stopped trading; the pair was closed at its last close.' },
        stop: {
          label: 'Stop-loss',
          hint: '|z| exceeded the stop level; no re-entry until z is back inside the entry band.',
        },
        entry: { label: 'Entry', hint: '|z| crossed the entry threshold.' },
        exit: { label: 'Exit', hint: 'The spread reverted to the exit level.' },
        vetoed: { label: 'Vetoed', hint: 'An entry filter rejected the signal.' },
        period_close: {
          label: 'Period close',
          hint: 'Closed because the quarterly pair re-selection started a new period.',
        },
        reselect: {
          label: 'Re-selection',
          hint: 'New formation window: pairs re-tested for cointegration and re-ranked.',
        },
      } as Record<string, EventText>,
    },

    fills: {
      title: (n: number) => `Fills (${n})`,
      summary: (notional: string, costs: string) => `traded ${notional} · costs ${costs}`,
      none: 'No fills yet.',
      filled: 'Filled',
      decided: 'Decided',
      ticker: 'Ticker',
      side: 'Side',
      shares: 'Shares',
      price: 'Price',
      notional: 'Notional',
      cost: 'Cost',
    },
  },
}

export type Messages = typeof en
