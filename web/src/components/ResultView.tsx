import { Link } from 'react-router-dom'
import type { BacktestDetail } from '../lib/api'
import { METRICS, humanize, longDate, num, pct } from '../lib/format'
import { PerformanceCharts, type Series } from './PerformanceCharts'
import { Card, StatTile } from './ui'

function paramText(params: BacktestDetail['params']) {
  return Object.entries(params)
    .filter(([, v]) => v !== null)
    .map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`)
    .join(' · ')
}

export function ResultView({ run, showPermalink = true }: { run: BacktestDetail; showPermalink?: boolean }) {
  const m = run.metrics
  const b = run.benchmark_metrics
  const vs = (key: string) => (b && m[key] != null && b[key] != null ? m[key]! - b[key]! : null)

  const series: Series[] = [
    { key: 'strategy', label: humanize(run.strategy), slot: 1, points: run.points },
    ...(run.benchmark ? [{ key: 'benchmark', label: 'SPY (buy & hold)', slot: 2, points: run.benchmark }] : []),
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-ink">
            {humanize(run.strategy)}{' '}
            <span className="font-normal text-ink-2" title={run.tickers.join(', ')}>
              · {run.tickers.length > 6 ? `${run.tickers.slice(0, 5).join(', ')} +${run.tickers.length - 5} more` : run.tickers.join(', ')}
            </span>
          </h2>
          <p className="text-xs text-muted">
            {longDate(run.start_date)} – {longDate(run.end_date)} · costs {(run.cost_rate * 1e4).toFixed(0)} bps
            {paramText(run.params) && ` · ${paramText(run.params)}`}
          </p>
        </div>
        {showPermalink && (
          <Link to={`/runs/${run.id}`} className="text-xs text-accent hover:underline">
            Saved as run #{run.id} →
          </Link>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Total return"
          value={pct(m.total_return)}
          delta={vs('total_return')}
          deltaLabel={b ? `${pct(vs('total_return'))} vs SPY` : undefined}
        />
        <StatTile label="CAGR" value={pct(m.cagr)} delta={vs('cagr')} deltaLabel={b ? `${pct(vs('cagr'))} vs SPY` : undefined} />
        <StatTile
          label="Sharpe ratio"
          value={num(m.sharpe)}
          delta={vs('sharpe')}
          deltaLabel={b ? `SPY ${num(b.sharpe)}` : undefined}
        />
        <StatTile
          label="Max drawdown"
          value={pct(m.max_drawdown)}
          delta={vs('max_drawdown')}
          deltaLabel={b ? `SPY ${pct(b.max_drawdown)}` : undefined}
        />
      </div>

      <PerformanceCharts series={series} />

      <Card title="All metrics">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-muted">
              <th className="py-2 font-medium">Metric</th>
              <th className="py-2 text-right font-medium">Strategy</th>
              {b && <th className="py-2 text-right font-medium">SPY</th>}
            </tr>
          </thead>
          <tbody className="tabular">
            {METRICS.filter((x) => x.key in m).map((x) => (
              <tr key={x.key} className="border-b border-line/50 last:border-0">
                <td className="py-1.5 text-ink-2">{x.label}</td>
                <td className="py-1.5 text-right text-ink">{x.fmt(m[x.key])}</td>
                {b && <td className="py-1.5 text-right text-ink-2">{x.key in b ? x.fmt(b[x.key]) : '—'}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
