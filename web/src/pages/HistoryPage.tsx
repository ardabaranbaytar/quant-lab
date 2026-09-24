import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { PerformanceCharts, type Series } from '../components/PerformanceCharts'
import { Card, ErrorBanner, Spinner } from '../components/ui'
import { api, type BacktestDetail, type BacktestSummary } from '../lib/api'
import { humanize, num, pct } from '../lib/format'

const MAX_COMPARE = 4

export function HistoryPage() {
  const [runs, setRuns] = useState<BacktestSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // run id -> colour slot. A run keeps its slot while selected, so toggling
  // another run never repaints it.
  const [slots, setSlots] = useState<Map<number, number>>(new Map())
  const [details, setDetails] = useState<Map<number, BacktestDetail>>(new Map())

  useEffect(() => {
    api.backtests().then(setRuns).catch((e: Error) => setError(e.message))
  }, [])

  const toggle = async (id: number) => {
    const next = new Map(slots)
    if (next.has(id)) {
      next.delete(id)
      setSlots(next)
      return
    }
    if (next.size >= MAX_COMPARE) return
    const used = new Set(next.values())
    const slot = [1, 2, 3, 4].find((s) => !used.has(s))!
    next.set(id, slot)
    setSlots(next)
    if (!details.has(id)) {
      try {
        const d = await api.backtest(id)
        setDetails((prev) => new Map(prev).set(id, d))
      } catch (e) {
        setError((e as Error).message)
      }
    }
  }

  const series: Series[] = useMemo(
    () =>
      [...slots]
        .filter(([id]) => details.has(id))
        .map(([id, slot]) => {
          const d = details.get(id)!
          return { key: `run${id}`, label: `#${id} ${humanize(d.strategy)}`, slot, points: d.points }
        }),
    [slots, details],
  )

  if (error) return <ErrorBanner message={error} />
  if (!runs) return <Spinner />

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-ink">Saved backtests</h1>
        <p className="text-sm text-ink-2">
          Every run is stored in MySQL. Select up to {MAX_COMPARE} to compare their equity curves.
        </p>
      </div>

      {series.length > 0 && <PerformanceCharts series={series} title="Comparison" />}

      <Card>
        {runs.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted">
            No runs yet. <Link to="/" className="text-accent hover:underline">Run your first backtest →</Link>
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className="w-8 py-2" />
                  <th className="py-2 pr-4 font-medium">Run</th>
                  <th className="py-2 pr-4 font-medium">Strategy</th>
                  <th className="py-2 pr-4 font-medium">Tickers</th>
                  <th className="py-2 pr-4 font-medium">Period</th>
                  <th className="py-2 pr-4 text-right font-medium">Return</th>
                  <th className="py-2 pr-4 text-right font-medium">Sharpe</th>
                  <th className="py-2 text-right font-medium">Max DD</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {runs.map((r) => {
                  const slot = slots.get(r.id)
                  const disabled = !slot && slots.size >= MAX_COMPARE
                  return (
                    <tr key={r.id} className="border-b border-line/50 last:border-0 hover:bg-surface-2/50">
                      <td className="py-2">
                        <label className="flex items-center gap-1.5">
                          <input
                            type="checkbox"
                            className="!w-auto"
                            checked={!!slot}
                            disabled={disabled}
                            onChange={() => toggle(r.id)}
                            aria-label={`Compare run ${r.id}`}
                          />
                          {slot && <span className="h-0.5 w-3 rounded" style={{ background: `var(--series-${slot})` }} />}
                        </label>
                      </td>
                      <td className="py-2 pr-4">
                        <Link to={`/runs/${r.id}`} className="text-accent hover:underline">#{r.id}</Link>
                      </td>
                      <td className="py-2 pr-4 text-ink">{humanize(r.strategy)}</td>
                      <td className="max-w-48 truncate py-2 pr-4 text-ink-2" title={r.tickers.join(', ')}>
                        {r.tickers.join(', ')}
                      </td>
                      <td className="whitespace-nowrap py-2 pr-4 text-ink-2">
                        {r.start_date.slice(0, 4)}–{r.end_date.slice(0, 4)}
                      </td>
                      <td className={`py-2 pr-4 text-right ${(r.metrics.total_return ?? 0) < 0 ? 'text-critical' : 'text-ink'}`}>
                        {pct(r.metrics.total_return)}
                      </td>
                      <td className="py-2 pr-4 text-right text-ink">{num(r.metrics.sharpe)}</td>
                      <td className="py-2 text-right text-ink-2">{pct(r.metrics.max_drawdown)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
