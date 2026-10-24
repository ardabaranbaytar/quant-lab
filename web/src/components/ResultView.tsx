import { Link } from 'react-router-dom'
import type { BacktestDetail } from '../lib/api'
import { useI18n } from '../i18n/context'
import { METRICS } from '../lib/format'
import { PerformanceCharts, type Series } from './PerformanceCharts'
import { Card, StatTile } from './ui'

export function ResultView({ run, showPermalink = true }: { run: BacktestDetail; showPermalink?: boolean }) {
  const { t, f, names } = useI18n()
  const paramText = Object.entries(run.params)
    .filter(([, v]) => v !== null)
    .map(([k, v]) => `${names.param(k)} ${v}`)
    .join(' · ')
  const m = run.metrics
  const b = run.benchmark_metrics
  const vs = (key: string) => (b && m[key] != null && b[key] != null ? m[key]! - b[key]! : null)

  const series: Series[] = [
    { key: 'strategy', label: names.strategy(run.strategy), slot: 1, points: run.points },
    ...(run.benchmark ? [{ key: 'benchmark', label: t.common.benchmark, slot: 2, points: run.benchmark }] : []),
  ]

  return (
    <div className="@container space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-ink">
            {names.strategy(run.strategy)}{' '}
            <span className="font-normal text-ink-2" title={run.tickers.join(', ')}>
              ·{' '}
              {run.tickers.length > 6
                ? `${run.tickers.slice(0, 5).join(', ')} ${t.result.moreTickers(run.tickers.length - 5)}`
                : run.tickers.join(', ')}
            </span>
          </h2>
          <p className="text-xs text-muted">
            {f.longDate(run.start_date)} – {f.longDate(run.end_date)} · {t.result.costs(Math.round(run.cost_rate * 1e4))}
            {paramText && ` · ${paramText}`}
          </p>
        </div>
        {showPermalink && (
          <Link to={`/runs/${run.id}`} className="text-xs text-accent hover:underline">
            {t.result.savedAs(run.id)}
          </Link>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label={t.result.totalReturn}
          value={f.pct(m.total_return)}
          delta={vs('total_return')}
          deltaLabel={b ? t.result.vsSpy(f.pct(vs('total_return'))) : undefined}
        />
        <StatTile
          label={t.result.cagr}
          value={f.pct(m.cagr)}
          delta={vs('cagr')}
          deltaLabel={b ? t.result.vsSpy(f.pct(vs('cagr'))) : undefined}
        />
        <StatTile
          label={t.result.sharpeRatio}
          value={f.num(m.sharpe)}
          delta={vs('sharpe')}
          deltaLabel={b ? t.result.spyValue(f.num(b.sharpe)) : undefined}
        />
        <StatTile
          label={t.result.maxDrawdown}
          value={f.pct(m.max_drawdown)}
          delta={vs('max_drawdown')}
          deltaLabel={b ? t.result.spyValue(f.pct(b.max_drawdown)) : undefined}
        />
      </div>

      {/* Wide: charts on the left, the metrics table beside them instead of far below. */}
      <div className="grid items-start gap-5 @6xl:grid-cols-[minmax(0,1fr)_26rem]">
        <PerformanceCharts series={series} />

        <Card title={t.result.allMetrics}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 font-medium">{t.result.metric}</th>
                <th className="py-2 text-right font-medium">{t.result.strategy}</th>
                {b && <th className="py-2 text-right font-medium">SPY</th>}
              </tr>
            </thead>
            <tbody className="tabular">
              {METRICS.filter((x) => x.key in m).map((x) => (
                <tr key={x.key} className="border-b border-line/50 last:border-0">
                  <td className="py-1.5 text-ink-2">{t.metrics[x.key] ?? x.key}</td>
                  <td className="py-1.5 text-right text-ink">{f.metric(x.kind, m[x.key])}</td>
                  {b && <td className="py-1.5 text-right text-ink-2">{x.key in b ? f.metric(x.kind, b[x.key]) : '—'}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  )
}
