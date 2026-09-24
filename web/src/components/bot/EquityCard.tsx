import { useMemo, useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { BotEquityPoint } from '../../lib/api'
import { equityRows, money, type EquityRow } from '../../lib/bot'
import { longDate, pct, signedPct } from '../../lib/format'
import { Card, Segmented } from '../ui'

const AXIS = { stroke: 'var(--axis)', fontSize: 11, tickLine: false, tick: { fill: 'var(--muted)' } }

const dayLabel = (iso: string) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { day: 'numeric', month: 'short' })

function RowTooltip({ active, row }: { active?: boolean; row?: EquityRow }) {
  if (!active || !row) return null
  const items: [string, string][] = [
    ['Equity', money(row.equity)],
    ['Return', signedPct(row.ret, 2)],
    ['Drawdown', pct(row.drawdown, 2)],
    ['Gross exposure', pct(row.gross_exposure)],
    ['Open pairs', String(row.open_pairs)],
  ]
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <div className="mb-1.5 font-medium text-ink">{longDate(row.date)}</div>
      {items.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-6">
          <span className="text-ink-2">{k}</span>
          <span className="tabular font-medium text-ink">{v}</span>
        </div>
      ))}
    </div>
  )
}

export function EquityCard({ points, capital }: { points: BotEquityPoint[]; capital: number }) {
  const [view, setView] = useState<'equity' | 'exposure'>('equity')
  const rows = useMemo(() => equityRows(points, capital), [points, capital])
  const maxDd = rows.reduce((m, r) => Math.min(m, r.drawdown), 0)

  const tooltip = (
    <Tooltip
      cursor={{ stroke: 'var(--muted)', strokeWidth: 1 }}
      isAnimationActive={false}
      content={(p) => <RowTooltip active={p.active} row={p.payload?.[0]?.payload as EquityRow | undefined} />}
    />
  )
  const xAxis = <XAxis dataKey="date" tickFormatter={dayLabel} minTickGap={32} {...AXIS} />

  return (
    <Card
      title="Equity curve"
      action={
        <Segmented
          value={view}
          onChange={setView}
          options={[
            { value: 'equity', label: 'Equity' },
            { value: 'exposure', label: 'Exposure' },
          ]}
        />
      }
    >
      {rows.length < 2 ? (
        <p className="py-10 text-center text-sm text-muted">
          The curve appears after the bot has processed two closes.
        </p>
      ) : (
        <>
          <div className="mb-1 flex flex-wrap justify-between gap-2 text-xs text-muted">
            <span>
              {view === 'equity'
                ? `Mark-to-market after each day's fills · dashed line = starting capital`
                : 'Gross exposure (area, left) and open pairs (line, right)'}
            </span>
            <span>max drawdown {pct(maxDd, 2)}</span>
          </div>
          <div className="h-72">
            <ResponsiveContainer>
              {view === 'equity' ? (
                <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 8 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  {xAxis}
                  <YAxis
                    {...AXIS}
                    width={64}
                    domain={['auto', 'auto']}
                    tickFormatter={(v: number) => money(v)}
                  />
                  <ReferenceLine y={capital} stroke="var(--axis)" strokeDasharray="4 4" />
                  {tooltip}
                  <Line
                    dataKey="equity"
                    stroke="var(--series-1)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              ) : (
                <ComposedChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 8 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  {xAxis}
                  <YAxis
                    yAxisId="gross"
                    {...AXIS}
                    width={44}
                    domain={[0, (max: number) => Math.max(1, Math.ceil(max * 10) / 10)]}
                    tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                  />
                  <YAxis yAxisId="pairs" orientation="right" {...AXIS} width={28} allowDecimals={false} />
                  {tooltip}
                  <Area
                    yAxisId="gross"
                    dataKey="gross_exposure"
                    stroke="var(--series-1)"
                    fill="var(--series-1)"
                    fillOpacity={0.12}
                    strokeWidth={1.5}
                    isAnimationActive={false}
                  />
                  <Line
                    yAxisId="pairs"
                    dataKey="open_pairs"
                    type="stepAfter"
                    stroke="var(--series-2)"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              )}
            </ResponsiveContainer>
          </div>
        </>
      )}
    </Card>
  )
}
