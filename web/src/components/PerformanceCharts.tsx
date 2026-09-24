import { useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Point } from '../lib/api'
import { longDate, pct, shortDate, yearlyReturns } from '../lib/format'
import { Card, Segmented } from './ui'

export interface Series {
  key: string
  label: string
  /** 1-based categorical slot; follows the entity, never its rank. */
  slot: number
  points: Point[]
}

const color = (slot: number) => `var(--series-${slot})`
const AXIS = { stroke: 'var(--axis)', fontSize: 11, tickLine: false, tick: { fill: 'var(--muted)' } }

type Row = { date: string } & Record<string, number | string | null>

function mergeSeries(series: Series[], field: 'equity' | 'drawdown'): Row[] {
  const rows = new Map<string, Row>()
  for (const s of series) {
    for (const p of s.points) {
      let row = rows.get(p.date)
      if (!row) rows.set(p.date, (row = { date: p.date }))
      row[s.key] = p[field]
    }
  }
  return [...rows.values()].sort((a, b) => a.date.localeCompare(b.date))
}

function yearTicks(rows: Row[]): string[] {
  const seen = new Set<string>()
  const ticks: string[] = []
  for (const r of rows) {
    const y = r.date.slice(0, 4)
    if (!seen.has(y)) {
      seen.add(y)
      ticks.push(r.date)
    }
  }
  // Thin out long ranges so labels never collide.
  const step = Math.ceil(ticks.length / 8)
  return ticks.filter((_, i) => i % step === 0)
}

function ChartTooltip({ active, payload, label, series, format }: {
  active?: boolean
  payload?: { dataKey: string; value: number }[]
  label?: string
  series: Series[]
  format: (v: number) => string
}) {
  if (!active || !payload?.length || !label) return null
  const byKey = new Map(payload.map((p) => [p.dataKey, p.value]))
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <div className="mb-1.5 font-medium text-ink">{longDate(label)}</div>
      {series.map((s) =>
        byKey.has(s.key) ? (
          <div key={s.key} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-ink-2">
              <span className="h-0.5 w-3 rounded" style={{ background: color(s.slot) }} />
              {s.label}
            </span>
            <span className="tabular font-medium text-ink">{format(byKey.get(s.key)!)}</span>
          </div>
        ) : null,
      )}
    </div>
  )
}

function Legend({ series }: { series: Series[] }) {
  if (series.length < 2) return null
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
      {series.map((s) => (
        <span key={s.key} className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded" style={{ background: color(s.slot) }} />
          {s.label}
        </span>
      ))}
    </div>
  )
}

function YearlyTable({ series }: { series: Series[] }) {
  const yearly = series.map((s) => yearlyReturns(s.points))
  const years = [...new Set(yearly.flatMap((m) => [...m.keys()]))].sort()
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th className="py-2 pr-4 font-medium">Year</th>
            {series.map((s) => (
              <th key={s.key} className="py-2 pr-4 text-right font-medium">{s.label}</th>
            ))}
          </tr>
        </thead>
        <tbody className="tabular">
          {years.map((y) => (
            <tr key={y} className="border-b border-line/50 last:border-0">
              <td className="py-1.5 pr-4 text-ink-2">{y}</td>
              {yearly.map((m, i) => {
                const v = m.get(y)
                return (
                  <td key={series[i].key} className={`py-1.5 pr-4 text-right ${v == null ? 'text-muted' : v < 0 ? 'text-critical' : 'text-ink'}`}>
                    {pct(v ?? null)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function PerformanceCharts({ series, title = 'Performance' }: { series: Series[]; title?: string }) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const [logScale, setLogScale] = useState(false)
  const equity = useMemo(() => mergeSeries(series, 'equity'), [series])
  const drawdown = useMemo(() => mergeSeries(series, 'drawdown'), [series])
  const ticks = useMemo(() => yearTicks(equity), [equity])
  // Clean drawdown ticks: 0, -5%, -10%… (or -10% steps for deep drawdowns).
  const ddTicks = useMemo(() => {
    const worst = Math.min(0, ...series.flatMap((s) => s.points.map((p) => p.drawdown)))
    const step = worst < -0.4 ? 0.2 : worst < -0.2 ? 0.1 : 0.05
    const floor = Math.floor(worst / step - 1e-9) * step
    return Array.from({ length: Math.round(-floor / step) + 1 }, (_, i) => -i * step)
  }, [series])

  const xAxis = (
    <XAxis dataKey="date" ticks={ticks} tickFormatter={(d: string) => d.slice(0, 4)} {...AXIS} minTickGap={24} />
  )
  const tooltip = (format: (v: number) => string) => (
    <Tooltip
      cursor={{ stroke: 'var(--muted)', strokeWidth: 1 }}
      isAnimationActive={false}
      content={(props) => (
        <ChartTooltip
          active={props.active}
          payload={props.payload as unknown as { dataKey: string; value: number }[]}
          label={props.label as string}
          series={series}
          format={format}
        />
      )}
    />
  )
  const growth = (v: number) => `${v.toFixed(2)}×  (${v >= 1 ? '+' : ''}${((v - 1) * 100).toFixed(1)}%)`

  return (
    <Card
      title={title}
      action={
        <Segmented
          value={view}
          onChange={setView}
          options={[
            { value: 'chart', label: 'Chart' },
            { value: 'table', label: 'Yearly table' },
          ]}
        />
      }
    >
      {view === 'table' ? (
        <YearlyTable series={series} />
      ) : (
        <div className="space-y-5">
          <Legend series={series} />
          <div>
            <div className="mb-1 flex items-center justify-between text-xs text-muted">
              <span>
                Growth of $1{equity.length > 0 && ` · ${shortDate(equity[0].date)} – ${shortDate(equity[equity.length - 1].date)}`}
              </span>
              <label className="flex items-center gap-1.5">
                <input type="checkbox" className="!w-auto" checked={logScale} onChange={(e) => setLogScale(e.target.checked)} />
                Log scale
              </label>
            </div>
            <div className="h-72">
              <ResponsiveContainer>
                <LineChart data={equity} syncId="perf" margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  {xAxis}
                  <YAxis
                    {...AXIS}
                    width={44}
                    scale={logScale ? 'log' : 'auto'}
                    domain={['auto', 'auto']}
                    allowDataOverflow={false}
                    tickFormatter={(v: number) => `${v < 10 ? v.toFixed(1) : v.toFixed(0)}×`}
                  />
                  <ReferenceLine y={1} stroke="var(--axis)" />
                  {tooltip(growth)}
                  {series.map((s) => (
                    <Line
                      key={s.key}
                      dataKey={s.key}
                      name={s.label}
                      stroke={color(s.slot)}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
                      isAnimationActive={false}
                      connectNulls={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div>
            <div className="mb-1 text-xs text-muted">Drawdown from peak</div>
            <div className="h-40">
              <ResponsiveContainer>
                <AreaChart data={drawdown} syncId="perf" margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  {xAxis}
                  <YAxis
                    {...AXIS}
                    width={44}
                    ticks={ddTicks}
                    domain={[ddTicks[ddTicks.length - 1], 0]}
                    tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                  />
                  {tooltip((v) => pct(v))}
                  {series.map((s) => (
                    <Area
                      key={s.key}
                      dataKey={s.key}
                      name={s.label}
                      stroke={color(s.slot)}
                      fill={color(s.slot)}
                      fillOpacity={0.1}
                      strokeWidth={1.5}
                      activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
                      isAnimationActive={false}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}
