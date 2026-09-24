export const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? '—' : `${(v * 100).toFixed(digits)}%`

export const num = (v: number | null | undefined, digits = 2) =>
  v == null ? '—' : v.toFixed(digits)

export const signedPct = (v: number | null | undefined, digits = 1) =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(digits)}%`

export const shortDate = (iso: string) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', year: 'numeric' })

export const longDate = (iso: string) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })

export const humanize = (name: string) =>
  name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()).replace(/\bTs\b/, 'TS')

/** Metric metadata: label, formatter, and whether higher is better. */
export const METRICS: { key: string; label: string; fmt: (v: number | null) => string }[] = [
  { key: 'total_return', label: 'Total return', fmt: (v) => pct(v) },
  { key: 'cagr', label: 'CAGR', fmt: (v) => pct(v) },
  { key: 'sharpe', label: 'Sharpe', fmt: (v) => num(v) },
  { key: 'max_drawdown', label: 'Max drawdown', fmt: (v) => pct(v) },
  { key: 'volatility', label: 'Volatility', fmt: (v) => pct(v) },
  { key: 'sortino', label: 'Sortino', fmt: (v) => num(v) },
  { key: 'calmar', label: 'Calmar', fmt: (v) => num(v) },
  { key: 'hit_rate', label: 'Hit rate', fmt: (v) => pct(v) },
  { key: 'annual_turnover', label: 'Annual turnover', fmt: (v) => (v == null ? '—' : `${v.toFixed(1)}×`) },
]

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
