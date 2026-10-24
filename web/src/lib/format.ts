/** Locale-aware formatters. Build once per language with `createFormat` (see i18n/LocaleProvider). */
export function createFormat(tag: string) {
  const numbers = new Map<string, Intl.NumberFormat>()
  const dates = new Map<string, Intl.DateTimeFormat>()

  const nf = (key: string, opts: Intl.NumberFormatOptions) => {
    let f = numbers.get(key)
    if (!f) numbers.set(key, (f = new Intl.NumberFormat(tag, opts)))
    return f
  }
  const df = (key: string, opts: Intl.DateTimeFormatOptions) => {
    let f = dates.get(key)
    if (!f) dates.set(key, (f = new Intl.DateTimeFormat(tag, opts)))
    return f
  }
  const fixed = (digits: number) => nf(`n${digits}`, { minimumFractionDigits: digits, maximumFractionDigits: digits })
  const day = (iso: string) => new Date(iso + 'T00:00:00')

  const pct = (v: number | null | undefined, digits = 1) =>
    v == null
      ? '—'
      : nf(`p${digits}`, { style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v)

  const num = (v: number | null | undefined, digits = 2) => (v == null ? '—' : fixed(digits).format(v))

  const turnover = (v: number | null | undefined) => (v == null ? '—' : `${fixed(1).format(v)}×`)

  return {
    pct,
    num,
    turnover,
    signedPct: (v: number | null | undefined, digits = 1) =>
      v == null
        ? '—'
        : nf(`sp${digits}`, {
            style: 'percent',
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
            signDisplay: 'exceptZero',
          }).format(v),
    /** A parameter value as typed: no forced decimals. */
    plain: (v: number) => nf('plain', { maximumFractionDigits: 4 }).format(v),
    shortDate: (iso: string) => df('short', { month: 'short', year: 'numeric' }).format(day(iso)),
    longDate: (iso: string) => df('long', { day: 'numeric', month: 'short', year: 'numeric' }).format(day(iso)),
    dayLabel: (iso: string) => df('day', { day: 'numeric', month: 'short' }).format(day(iso)),
    money: (v: number | null | undefined, digits = 0) =>
      v == null
        ? '—'
        : nf(`m${digits}`, {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
          }).format(v),
    shares: (v: number) => nf(Math.abs(v) < 10 ? 'sh3' : 'sh1', { maximumFractionDigits: Math.abs(v) < 10 ? 3 : 1 }).format(Math.abs(v)),
    metric: (kind: MetricKind, v: number | null) => (kind === 'pct' ? pct(v) : kind === 'num' ? num(v) : turnover(v)),
  }
}

export type Formatters = ReturnType<typeof createFormat>

export type MetricKind = 'pct' | 'num' | 'turnover'

/** Metrics shown in the "All metrics" table, in order; labels live in the message files. */
export const METRICS: { key: string; kind: MetricKind }[] = [
  { key: 'total_return', kind: 'pct' },
  { key: 'cagr', kind: 'pct' },
  { key: 'sharpe', kind: 'num' },
  { key: 'max_drawdown', kind: 'pct' },
  { key: 'volatility', kind: 'pct' },
  { key: 'sortino', kind: 'num' },
  { key: 'calmar', kind: 'num' },
  { key: 'hit_rate', kind: 'pct' },
  { key: 'annual_turnover', kind: 'turnover' },
]

export const humanize = (name: string) =>
  name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()).replace(/\bTs\b/, 'TS')

export function yearlyReturns(points: { date: string; equity: number }[]) {
  const byYear = new Map<string, { first: number; last: number }>()
  let prev = 1
  for (const p of points) {
    const y = p.date.slice(0, 4)
    const entry = byYear.get(y)
    if (!entry) byYear.set(y, { first: prev, last: p.equity })
    else entry.last = p.equity
    prev = p.equity
  }
  return new Map([...byYear].map(([y, { first, last }]) => [y, last / first - 1]))
}
